(() => {
    const theme = matchMedia('(prefers-color-scheme: dark)');
    const setTheme = () => document.documentElement.setAttribute('data-bs-theme', theme.matches ? 'dark' : 'light');
    setTheme();
    theme.addEventListener('change', setTheme);
    document.addEventListener('play', event => {
        if (!(event.target instanceof HTMLAudioElement)) return;
        document.querySelectorAll('audio').forEach(audio => { if (audio !== event.target) audio.pause(); });
    }, true);
    document.addEventListener('keydown', event => {
        if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
            event.preventDefault();
            document.getElementById('generate')?.click();
        }
    });
    window.voiceLab = {
        replay: async id => {
            const audio = document.getElementById(id);
            if (audio) { audio.currentTime = 0; await audio.play(); }
        },
        readDraft: () => {
            try { return JSON.parse(sessionStorage.getItem('voice-lab-draft')); }
            catch { return null; }
        },
        saveDraft: draft => { try { sessionStorage.setItem('voice-lab-draft', JSON.stringify(draft)); } catch { /* Drafts are optional; generated history is on disk. */ } }
    };
})();
