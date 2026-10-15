using System.Diagnostics;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace VoiceLab;

public sealed record SpeechRequest(string Text, string Engine = "kokoro", string? Voice = "af_heart", double Speed = 1, int ParagraphPauseMs = 250);
public sealed record SpeechRun(string Id, DateTimeOffset CreatedUtc, SpeechRequest Request,
    string Status = "generating", string? Error = null, double AudioSeconds = 0,
    double StartupMs = 0, double GenerationMs = 0, double TotalMs = 0, double GenerationRtf = 0,
    long SaturatedSamples = 0, Dictionary<string, string>? Artifacts = null);
public sealed record Preset(string Id, string Name, string Engine, string? Voice, double Speed, int ParagraphPauseMs);
public sealed record Feedback(string Id, string A, string B, string Preference, string Note, DateTimeOffset CreatedUtc);
public sealed record LibraryState(List<Preset> Presets, List<Feedback> Feedback);
public sealed record VoiceChoice(string Id, string Name);
public sealed record EngineChoice(string Id, string Name, bool Available, string? Reason, List<VoiceChoice> Voices);

/// <summary>One local writer, one synthesis process. Completed receipts are never edited.</summary>
public sealed class SpeechService : IAsyncDisposable
{
    public static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web) { WriteIndented = true };
    private readonly string root, stateRoot, workRoot, receiptRoot;
    private readonly object gate = new();
    private readonly FileStream writerLock;
    private readonly ILogger<SpeechService> logger;
    private LibraryState library;
    private SpeechRun? active;
    private CancellationTokenSource? cancellation;
    private Task? running;
    public bool Diagnostics { get; }
    public string? StorageWarning { get; private set; }

    public SpeechService(IConfiguration config, IWebHostEnvironment env, ILogger<SpeechService> log)
    {
        logger = log;
        root = Path.GetFullPath(config["repo-root"] ?? Path.Combine(env.ContentRootPath, "../.."));
        if (!File.Exists(Path.Combine(root, "src/subtitle_lab/cli.py"))) throw new InvalidOperationException("Set --repo-root to the Subtitle Lab checkout.");
        Diagnostics = config.GetValue<bool>("diagnostics");
        stateRoot = Path.Combine(root, "output/voice-lab");
        workRoot = Path.Combine(stateRoot, "work");
        receiptRoot = Path.Combine(root, "output/RECEIPTS");
        Directory.CreateDirectory(workRoot);
        Directory.CreateDirectory(receiptRoot);
        writerLock = new FileStream(Path.Combine(stateRoot, "writer.lock"), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
        library = ReadLibrary();
        RecoverInterrupted();
    }

    public SpeechRun? Active { get { lock (gate) return active; } }
    public LibraryState Library { get { lock (gate) return new([.. library.Presets], [.. library.Feedback]); } }

    public List<EngineChoice> Engines()
    {
        bool Has(string path) => File.Exists(Path.Combine(root, path));
        var voices = new List<VoiceChoice>();
        foreach (var (id, name) in new[] { ("af_heart", "Heart"), ("af_bella", "Bella"), ("am_michael", "Michael") })
            if (Has($"models/kokoro/voices/{id}.pt")) voices.Add(new(id, name));
        var kokoro = Has(".venv-kokoro/bin/python") && Has("models/kokoro/kokoro-v1_0.pth") && Has("models/kokoro/config.json") && voices.Count > 0;
        var piper = Has(".venv/bin/python") && Has("models/piper/en_US-lessac-medium.onnx") && Has("models/piper/en_US-lessac-medium.onnx.json") && Has(".venv/bin/ffmpeg");
        var result = new List<EngineChoice> {
            new("kokoro", "Kokoro", kokoro, kokoro ? null : "Needs the local Kokoro environment, model, and stock voices.", voices),
            new("piper-local", "Piper · Lessac", piper, piper ? null : "Needs the local Piper environment, Lessac model, and FFmpeg.", [])
        };
        if (Diagnostics) result.Add(new("tone", "Tone · diagnostic only", true, null, []));
        return result;
    }

    public SpeechRun Start(SpeechRequest request)
    {
        request = Validate(request);
        lock (gate)
        {
            if (active is not null) throw new InvalidOperationException("A generation is already running. Wait or cancel it first.");
            var run = new SpeechRun($"text-{DateTime.UtcNow:yyyyMMddTHHmmssfff}-{Guid.NewGuid():N}", DateTimeOffset.UtcNow, request);
            var stage = Path.Combine(workRoot, run.Id);
            Directory.CreateDirectory(stage);
            WriteJson(Path.Combine(stage, "request.json"), run);
            File.WriteAllText(Path.Combine(stage, "input.txt"), request.Text, new UTF8Encoding(false));
            cancellation = new();
            var token = cancellation.Token;
            active = run;
            // Linux parent-death signals bind to the creating thread. Keep that
            // thread alive for the worker's lifetime instead of using an idle
            // thread-pool thread that could retire during a long synthesis.
            running = Task.Factory.StartNew(() => Execute(run, stage, token).GetAwaiter().GetResult(),
                CancellationToken.None, TaskCreationOptions.LongRunning, TaskScheduler.Default);
            return run;
        }
    }

    private SpeechRequest Validate(SpeechRequest r)
    {
        if (string.IsNullOrWhiteSpace(r.Text)) throw new ArgumentException("Paste some text before generating speech.");
        if (r.Text.EnumerateRunes().Count() > 5000 || r.Text.Contains('\0')) throw new ArgumentException("Use up to 5,000 characters, without NUL characters.");
        if (!double.IsFinite(r.Speed) || r.Speed < .5 || r.Speed > 2) throw new ArgumentException("Speech speed must be from 0.5 to 2.0.");
        if (r.ParagraphPauseMs < 0 || r.ParagraphPauseMs > 1500) throw new ArgumentException("Paragraph gap must be from 0 to 1,500 ms.");
        var engine = Engines().SingleOrDefault(e => e.Id == r.Engine) ?? throw new ArgumentException("Choose an installed engine.");
        if (!engine.Available) throw new ArgumentException(engine.Reason);
        if (r.Engine == "kokoro" && !engine.Voices.Any(v => v.Id == r.Voice)) throw new ArgumentException("Choose an installed voice.");
        return r with { Voice = r.Engine == "kokoro" ? r.Voice : null };
    }

    public void Cancel() { lock (gate) cancellation?.Cancel(); }

    private async Task Execute(SpeechRun run, string stage, CancellationToken token)
    {
        var timer = Stopwatch.StartNew();
        try
        {
            var r = run.Request;
            var python = r.Engine switch { "kokoro" => Path.Combine(root, ".venv-kokoro/bin/python"), "piper-local" => Path.Combine(root, ".venv/bin/python"), _ => "/usr/bin/python3" };
            var info = new ProcessStartInfo(python) { WorkingDirectory = root, UseShellExecute = false, RedirectStandardOutput = true, RedirectStandardError = true };
            foreach (var arg in new[] { "-m", "subtitle_lab", "speak", "--text-file", Path.Combine(stage, "input.txt"),
                "--engine", r.Engine, "--speed", r.Speed.ToString(CultureInfo.InvariantCulture),
                "--paragraph-pause-ms", r.ParagraphPauseMs.ToString(CultureInfo.InvariantCulture), "--threads", "2",
                "--parent-pid", Environment.ProcessId.ToString(CultureInfo.InvariantCulture), "--out", Path.Combine(stage, "speech") }) info.ArgumentList.Add(arg);
            if (r.Voice is not null) { info.ArgumentList.Add("--voice"); info.ArgumentList.Add(r.Voice); }
            info.Environment["PYTHONPATH"] = Path.Combine(root, "src");
            info.Environment["PATH"] = Path.Combine(root, ".venv/bin") + ":" + Environment.GetEnvironmentVariable("PATH");
            info.Environment["HF_HUB_OFFLINE"] = "1";
            info.Environment["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1";
            info.Environment["HF_HOME"] = Path.Combine(root, ".cache/huggingface");
            info.Environment["XDG_CACHE_HOME"] = Path.Combine(root, ".cache");
            info.Environment["TORCH_HOME"] = Path.Combine(root, ".cache/torch");
            info.Environment["TMPDIR"] = Path.Combine(root, ".cache/tmp");
            Directory.CreateDirectory(info.Environment["TMPDIR"]!);
            WriteJson(Path.Combine(stage, "command.json"), new { executable = python, arguments = info.ArgumentList.ToArray(), workingDirectory = root, dotnet = Environment.Version.ToString(), os = Environment.OSVersion.ToString() });
            using var process = new Process { StartInfo = info };
            token.ThrowIfCancellationRequested();
            if (!process.Start()) throw new IOException("Could not start the speech process.");
            using var registration = token.Register(() => {
                try { process.Kill(entireProcessTree: true); } catch (InvalidOperationException) { }
            });
            await using var stdout = File.Create(Path.Combine(stage, "stdout.json"));
            await using var stderr = File.Create(Path.Combine(stage, "stderr.log"));
            await Task.WhenAll(process.StandardOutput.BaseStream.CopyToAsync(stdout), process.StandardError.BaseStream.CopyToAsync(stderr), process.WaitForExitAsync());
            await stdout.FlushAsync();
            await stderr.FlushAsync();
            stdout.Close();
            stderr.Close();
            token.ThrowIfCancellationRequested();
            if (process.ExitCode != 0) {
                var detail = File.ReadLines(Path.Combine(stage, "stderr.log")).LastOrDefault(s => !string.IsNullOrWhiteSpace(s)) ?? "No error detail returned.";
                if (detail.Length > 500) detail = detail[..500];
                throw new IOException($"Speech exited with code {process.ExitCode}: {detail}");
            }
            using var manifest = JsonDocument.Parse(await File.ReadAllTextAsync(Path.Combine(stage, "speech/manifest.json")));
            var m = manifest.RootElement.GetProperty("metrics");
            if (!File.Exists(Path.Combine(stage, "speech/speech.wav"))) throw new IOException("Speech process produced no audio.");
            run = run with { Status = "completed", AudioSeconds = m.GetProperty("audio_ms").GetDouble() / 1000,
                StartupMs = m.GetProperty("startup_ms").GetDouble(), GenerationMs = m.GetProperty("generation_ms").GetDouble(),
                GenerationRtf = m.GetProperty("generation_rtf").GetDouble(), SaturatedSamples = m.GetProperty("saturated_pcm_samples").GetInt64() };
        }
        catch (OperationCanceledException) { run = run with { Status = "canceled", Error = "Generation canceled; partial files retained in receipt." }; }
        catch (Exception ex) { run = run with { Status = "failed", Error = ex.Message }; logger.LogWarning("Speech {Id}: {Error}", run.Id, ex.Message); }
        finally
        {
            run = run with { TotalMs = timer.Elapsed.TotalMilliseconds };
            try { Seal(run, stage); }
            catch (Exception ex) { StorageWarning = $"Could not finalize {run.Id}: {ex.Message}. Staged files retained."; logger.LogError(ex, "Receipt finalization"); }
            lock (gate) { active = null; cancellation?.Dispose(); cancellation = null; }
        }
    }

    private void Seal(SpeechRun run, string stage)
    {
        var hashes = Directory.EnumerateFiles(stage, "*", SearchOption.AllDirectories)
            .Where(p => Path.GetFileName(p) != "run.json")
            .ToDictionary(p => Path.GetRelativePath(stage, p), p => {
                using var file = File.OpenRead(p);
                return Convert.ToHexString(SHA256.HashData(file)).ToLowerInvariant();
            });
        WriteJson(Path.Combine(stage, "run.json"), run with { Artifacts = hashes });
        Directory.Move(stage, Path.Combine(receiptRoot, run.Id));
    }

    private void RecoverInterrupted()
    {
        foreach (var stage in Directory.EnumerateDirectories(workRoot))
        {
            var request = Path.Combine(stage, "request.json");
            if (!File.Exists(request)) continue;
            var run = JsonSerializer.Deserialize<SpeechRun>(File.ReadAllText(request), Json);
            if (run is not null) Seal(run with { Status = "interrupted", Error = "Application stopped before this request was finalized." }, stage);
        }
    }

    public List<SpeechRun> History()
    {
        var result = new List<SpeechRun>();
        foreach (var directory in Directory.EnumerateDirectories(receiptRoot, "text-*"))
        {
            var path = Path.Combine(directory, "run.json");
            if (!File.Exists(path)) continue;
            try {
                var item = JsonSerializer.Deserialize<SpeechRun>(File.ReadAllText(path), Json);
                if (item is not null && item.Id == Path.GetFileName(directory)) result.Add(item);
            }
            catch (Exception ex) when (ex is IOException or JsonException) { StorageWarning = $"Unreadable history record: {Path.GetFileName(directory)}"; }
        }
        return result.OrderByDescending(r => r.CreatedUtc).ToList();
    }

    public SpeechRun? Find(string id) => ValidId(id) ? History().FirstOrDefault(r => r.Id == id) : null;
    private static bool ValidId(string id) => id.StartsWith("text-", StringComparison.Ordinal) && id.All(c => char.IsAsciiLetterOrDigit(c) || c == '-') && id.Length < 100;
    public string? AudioPath(string id)
    {
        var run = Find(id);
        if (run?.Status != "completed") return null;
        var path = Path.Combine(receiptRoot, id, "speech/speech.wav");
        return File.Exists(path) ? path : null;
    }

    public Preset SavePreset(string name, SpeechRequest request)
    {
        request = Validate(request);
        name = name.Trim();
        if (name.Length is < 1 or > 80) throw new ArgumentException("Preset name must contain 1–80 characters.");
        lock (gate)
        {
            if (library.Presets.Any(p => p.Name.Equals(name, StringComparison.OrdinalIgnoreCase))) throw new ArgumentException("That preset name already exists. Choose a new name.");
            var preset = new Preset(Guid.NewGuid().ToString("N"), name, request.Engine, request.Voice, request.Speed, request.ParagraphPauseMs);
            var next = library with { Presets = [.. library.Presets, preset] };
            WriteJson(Path.Combine(stateRoot, "library.json"), next);
            library = next;
            return preset;
        }
    }

    public void SaveFeedback(string a, string b, string preference, string note)
    {
        if (a == b || Find(a)?.Status != "completed" || Find(b)?.Status != "completed") throw new ArgumentException("Choose two different completed results to compare.");
        if (preference is not ("A" or "B" or "same")) throw new ArgumentException("Choose A, B, or no clear difference.");
        if (note.Length > 2000) throw new ArgumentException("Keep the note under 2,000 characters.");
        lock (gate)
        {
            var next = library with { Feedback = [.. library.Feedback, new(Guid.NewGuid().ToString("N"), a, b, preference, note, DateTimeOffset.UtcNow)] };
            WriteJson(Path.Combine(stateRoot, "library.json"), next);
            library = next;
        }
    }

    private LibraryState ReadLibrary()
    {
        var path = Path.Combine(stateRoot, "library.json");
        if (!File.Exists(path)) return new([], []);
        return JsonSerializer.Deserialize<LibraryState>(File.ReadAllText(path), Json) ?? throw new InvalidDataException("Local library is unreadable; original file was preserved.");
    }

    private static void WriteJson<T>(string path, T value)
    {
        var temp = path + ".tmp";
        File.WriteAllText(temp, JsonSerializer.Serialize(value, Json) + "\n", new UTF8Encoding(false));
        File.Move(temp, path, overwrite: true);
    }

    public async ValueTask DisposeAsync()
    {
        Cancel();
        if (running is not null) await running;
        writerLock.Dispose();
    }
}
