using Microsoft.AspNetCore.DataProtection;
using VoiceLab;
using VoiceLab.Components;

var builder = WebApplication.CreateBuilder(args);
// The local launcher runs built (not published) assets without a launch profile.
builder.WebHost.UseStaticWebAssets();
builder.Services.AddRazorComponents().AddInteractiveServerComponents()
    .AddHubOptions(options => options.MaximumReceiveMessageSize = 128 * 1024);
builder.Services.AddSingleton<SpeechService>();
builder.Services.AddDataProtection().PersistKeysToFileSystem(new DirectoryInfo(
    Path.Combine(Path.GetFullPath(builder.Configuration["repo-root"] ?? Path.Combine(builder.Environment.ContentRootPath, "../..")),
        ".cache/voice-lab-keys")));
var app = builder.Build();
app.Use(async (context, next) => {
    if (context.Connection.RemoteIpAddress is { } ip && !System.Net.IPAddress.IsLoopback(ip)) {
        context.Response.StatusCode = 403; return;
    }
    if (context.Request.Host.Host is not ("localhost" or "127.0.0.1" or "[::1]")) {
        context.Response.StatusCode = 403; return;
    }
    var origin = context.Request.Headers.Origin.ToString();
    if (origin.Length > 0 && origin != $"{context.Request.Scheme}://{context.Request.Host}") {
        context.Response.StatusCode = 403; return;
    }
    await next();
});
if (!app.Environment.IsDevelopment()) app.UseExceptionHandler("/Error", createScopeForErrors: true);
app.UseAntiforgery();
app.MapStaticAssets();
app.MapGet("/audio/{id}", (string id, bool? download, SpeechService speech) => {
    var path = speech.AudioPath(id);
    return path is null ? Results.NotFound() : Results.File(path, "audio/wav",
        fileDownloadName: download == true ? $"{id}.wav" : null, enableRangeProcessing: true);
});
app.MapGet("/receipt/{id}", (string id, SpeechService speech) =>
    speech.Find(id) is { } run ? Results.Json(run, SpeechService.Json) : Results.NotFound());
app.MapGet("/health", (SpeechService speech) => Results.Json(new { status = "ready", engines = speech.Engines() }));
app.MapRazorComponents<App>().AddInteractiveServerRenderMode();
var service = app.Services.GetRequiredService<SpeechService>();
app.Lifetime.ApplicationStopping.Register(service.Cancel);
app.Run();
