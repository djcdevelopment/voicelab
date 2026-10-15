#!/usr/bin/env python3
"""Verify native single-file playback/pause/seek with a fresh, muted browser.

Requires isolated Playwright + Chromium. Does not access an operator browser profile.
"""
from pathlib import Path
import argparse
import json
import os
import sys
import time
from hashlib import sha256
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from subtitle_lab.pipeline import validate


def verify_voice_lab(args):
    """Exercise the real local Blazor UI; all ratings here are storage probes only."""
    from playwright.sync_api import sync_playwright, expect
    args.out.mkdir(parents=True, exist_ok=False)
    result = {'url': args.url, 'checks': [], 'runs': [], 'audio_muted_for_automation': True,
              'listener_verdict': 'not assessed'}
    phrase = 'A quiet morning gives us time to think.\n\nLet us listen carefully, then try a different voice.'
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=['--disable-gpu'])
            page = browser.new_page(viewport={'width':1440,'height':1100})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.set_default_timeout(15000)
            page.goto(args.url)
            expect(page.locator('#text')).to_be_visible()
            page.locator('#text').fill('')
            expect(page.locator('#generate')).to_be_disabled()
            page.locator('#text').fill('x'*5001)
            expect(page.locator('#generate')).to_be_disabled()
            page.locator('#text').fill(phrase)
            result['checks'].append('empty and oversized input disabled')

            def slider(name, value):
                page.locator('#'+name).evaluate('(el, value) => {el.value=value;el.dispatchEvent(new Event("input", {bubbles:true}));}', str(value))
                label = page.locator(f'label[for="{name}"]')
                expect(label).to_contain_text(f'{float(value):.2f}' if name == 'speed' else str(value))

            def generate(engine, voice=None, keyboard=False):
                page.locator('#engine').select_option(engine)
                if voice: page.locator('#voice').select_option(voice)
                card = page.locator('[data-testid="result"]').nth(1)
                old = card.get_attribute('data-run-id')
                expect(page.locator('#generate')).to_be_enabled()
                if keyboard: page.locator('#text').press('Control+Enter')
                else: page.locator('#generate').click()
                deadline = time.monotonic()+180
                while time.monotonic() < deadline:
                    new = card.get_attribute('data-run-id')
                    if new and new != old:
                        record = page.request.get(args.url.rstrip('/')+'/receipt/'+new).json()
                        if record['status'] != 'completed':
                            raise AssertionError(record)
                        root = ROOT/'output/RECEIPTS'/new
                        for name, digest in record['artifacts'].items():
                            assert sha256((root/name).read_bytes()).hexdigest() == digest, name
                        validate(root/'speech')
                        assert record['request']['text'] == phrase
                        assert record['request']['engine'] == engine
                        if voice: assert record['request']['voice'] == voice
                        result['runs'].append(record)
                        return record
                    page.wait_for_timeout(200)
                raise AssertionError('generation did not complete')

            slider('speed', 1)
            slider('gap', 250)
            first = generate('tone', keyboard=True)
            page.get_by_role('button', name='Pin as A', exact=True).click()
            slider('gap', 500)
            second = generate('tone')
            assert second['request']['paragraphPauseMs'] == 500
            assert abs(second['audioSeconds'] - first['audioSeconds'] - .25) < .002
            expect(page.locator('[data-testid="comparison"]')).to_contain_text('Same text')
            expect(page.locator('[data-testid="comparison"]')).to_contain_text('250 → 500')
            result['checks'].append('Ctrl+Enter generation, exact gap propagation, source and artifact integrity, comparison labels')
            audios = page.locator('audio')
            audios.evaluate_all('(nodes) => nodes.forEach(a => {a.muted=true;})')
            audios.nth(0).evaluate('(a) => a.play()')
            page.wait_for_timeout(600)
            assert audios.nth(0).evaluate('(a) => a.currentTime') > .2
            audios.nth(1).evaluate('(a) => a.play()')
            expect(audios.nth(0)).to_have_js_property('paused', True)
            audios.nth(1).evaluate('(a) => a.pause()')
            paused = audios.nth(1).evaluate('(a) => a.currentTime')
            page.wait_for_timeout(300)
            assert abs(audios.nth(1).evaluate('(a) => a.currentTime')-paused) < .01
            for target in (1.5, .3):
                audios.nth(1).evaluate('''(a,t) => new Promise(resolve => {
                    a.addEventListener('seeked', resolve, {once:true}); a.currentTime=t;
                })''', target)
                assert abs(audios.nth(1).evaluate('(a)=>a.currentTime')-target) < .05
            response = page.request.get(args.url.rstrip('/')+'/audio/'+second['id'], headers={'Range':'bytes=0-99'})
            assert response.status == 206 and len(response.body()) == 100
            download = page.request.get(args.url.rstrip('/')+'/audio/'+second['id']+'?download=true')
            assert 'attachment' in download.headers['content-disposition']
            result['checks'].append('play, pause, forward/back seek, exclusive playback, HTTP range and download')

            page.locator('#note').fill('Automation storage probe only; no human listening verdict.')
            page.get_by_role('button', name='No clear difference', exact=True).click()
            expect(page.get_by_role('status').filter(has_text='Listening preference saved.')).to_be_visible()
            preset = 'Automation gap '+str(int(time.time()))
            page.locator('#preset-name').fill(preset)
            page.locator('#save-preset').click()
            expect(page.locator('#presets option').filter(has_text=preset)).to_have_count(1)
            page.reload()
            expect(page.locator('#text')).to_have_value(phrase)
            expect(page.locator('#presets option').filter(has_text=preset)).to_have_count(1)
            slider('gap', 0)
            page.locator('#presets').select_option(label=preset)
            expect(page.locator('#gap')).to_have_value('500')
            result['preset'] = preset
            result['checks'].append('preference persistence, preset save/restore, history and draft survive reload')

            # Cancel an actual model startup; no background jobs may remain busy.
            page.locator('#engine').select_option('kokoro')
            page.locator('#generate').click()
            expect(page.locator('#cancel')).to_be_enabled()
            # A second tab observes the globally owned request.
            other = browser.new_page()
            other.goto(args.url)
            expect(other.locator('#text')).to_be_visible()
            other.locator('#text').fill(phrase)
            expect(other.locator('#generate')).to_be_disabled()
            page.locator('#cancel').click()
            expect(page.locator('[data-testid="status"]')).to_contain_text('Ready', timeout=15000)
            expect(page.locator('[data-testid="result"]').nth(1)).to_contain_text('canceled')
            other.close()
            result['checks'].append('global single generation across tabs and cancellation')

            if args.real_speech:
                slider('gap', 250)
                slider('speed', 1)
                generate('kokoro', 'af_heart')
                page.get_by_role('button', name='Pin as A', exact=True).click()
                generate('kokoro', 'af_bella')
                slider('speed', 1.10)
                faster = generate('kokoro', 'af_bella')
                assert faster['request']['speed'] == 1.1
                slider('speed', 1)
                generate('piper-local')
                result['checks'].append('real Heart, Bella, Bella speed 1.10, Piper speech and receipt validation')
            page.screenshot(path=str(args.out/'desktop.png'), full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(args.out/'mobile.png'), full_page=True)
            page.emulate_media(color_scheme='dark')
            expect(page.locator('html')).to_have_attribute('data-bs-theme', 'dark')
            page.screenshot(path=str(args.out/'dark.png'), full_page=True)
            result['checks'].append('mobile without horizontal overflow and system dark theme')
            assert not errors, errors
            result['status'] = 'PASS'
            browser.close()
    except Exception as exc:
        result.update(status='FAIL', exception=type(exc).__name__, message=str(exc))
        raise
    finally:
        (args.out/'browser-check.json').write_text(json.dumps(result, indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',required=True)
    parser.add_argument('--render',type=Path)
    parser.add_argument('--voice-lab',action='store_true',help='Check Voice Lab UI (launch with --diagnostics)')
    parser.add_argument('--real-speech',action='store_true',help='Also synthesize installed Heart, Bella and Piper voices')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    url=urlparse(args.url)
    if url.scheme!='http' or url.hostname not in ('127.0.0.1','localhost') or url.username or url.query:
        parser.error('Use an unauthenticated loopback HTTP player URL')
    os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',str(ROOT/'.cache/playwright'))
    os.environ['TMPDIR']=str(ROOT/'.cache/browser-tmp')
    Path(os.environ['TMPDIR']).mkdir(parents=True,exist_ok=True)
    if args.voice_lab:
        return verify_voice_lab(args)
    if args.render is None:
        parser.error('--render is required for the subtitle video check')
    validate(args.render)
    cues=json.loads((args.render/'manifest.json').read_text())['cues']
    if len(cues)<2:parser.error('Playback verification requires at least two cues')
    args.out.mkdir(parents=True,exist_ok=False)
    os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',str(ROOT/'.cache/playwright'))
    os.environ['TMPDIR']=str(ROOT/'.cache/browser-tmp')
    Path(os.environ['TMPDIR']).mkdir(parents=True,exist_ok=True)
    from playwright.sync_api import sync_playwright
    result={'url':args.url,'checks':[],'audio_muted_for_automation':True}
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True,args=['--disable-gpu'])
            result['browser_version']=browser.version
            page=browser.new_page()
            console=[]
            page.on('console',lambda message:console.append({'type':message.type,'text':message.text}))
            result['console']=console
            page.set_default_timeout(15000)
            page.goto(args.url)
            page.wait_for_function('document.querySelector("video")?.readyState >= 2')
            result['metadata']=page.evaluate('''() => {
                const v=document.querySelector('video');v.muted=true;
                if(v.textTracks.length) v.textTracks[0].mode='showing';
                return {duration:v.duration,width:v.videoWidth,height:v.videoHeight,videoElements:document.querySelectorAll('video').length,audioElements:document.querySelectorAll('audio').length};
            }''')
            assert result['metadata']['videoElements']==1 and result['metadata']['audioElements']==0
            page.evaluate('document.querySelector("video").play()')
            first=page.evaluate('document.querySelector("video").currentTime')
            page.wait_for_timeout(750)
            advanced=page.evaluate('document.querySelector("video").currentTime')
            assert advanced-first>.4
            result['checks'].append({'check':'play advances','advance_s':advanced-first})
            page.evaluate('document.querySelector("video").pause()')
            paused=page.evaluate('document.querySelector("video").currentTime')
            page.wait_for_timeout(500)
            after=page.evaluate('document.querySelector("video").currentTime')
            assert abs(after-paused)<.01
            result['checks'].append({'check':'pause holds shared clock','delta_s':after-paused})
            # Forward and backward seeks: observe both clock and active caption.
            for cue in [cues[1],cues[0]]:
                target=(cue['start_ms']+cue['end_ms'])/2000
                page.evaluate('''target => new Promise((resolve,reject)=>{
                    const v=document.querySelector('video');
                    const timer=setTimeout(()=>reject(new Error('seek timeout')),10000);
                    v.addEventListener('seeked',()=>{clearTimeout(timer);resolve();},{once:true});v.currentTime=target;
                })''',target)
                result['last_seek_state']=page.evaluate('''() => {const v=document.querySelector('video');return {currentTime:v.currentTime,paused:v.paused,trackReadyState:document.querySelector('track').readyState,tracks:[...v.textTracks].map(t=>({mode:t.mode,cues:[...(t.cues||[])].map(c=>({start:c.startTime,end:c.endTime,text:c.text})),active:[...(t.activeCues||[])].map(c=>c.text)}))};}''')
                page.wait_for_function('''text => [...(document.querySelector('video').textTracks[0]?.activeCues||[])].some(c=>c.text===text)''',arg=cue['text'])
                state=page.evaluate('''() => {const v=document.querySelector('video');return {currentTime:v.currentTime,paused:v.paused,text:[...(v.textTracks[0]?.activeCues||[])].map(c=>c.text)};}''')
                assert abs(state['currentTime']-target)<.03 and state['paused']
                result['checks'].append({'check':'seek + caption','target_s':target,**state})
            page.screenshot(path=str(args.out/'paused-caption.png'))
            page.evaluate('document.querySelector("video").play()')
            frame=page.evaluate('''() => Promise.race([
                new Promise(resolve=>document.querySelector('video').requestVideoFrameCallback((_,m)=>resolve({frameMediaTime:m.mediaTime,clock:document.querySelector('video').currentTime}))),
                new Promise((_,reject)=>setTimeout(()=>reject(new Error('frame timeout')),5000))])''')
            assert abs(frame['frameMediaTime']-frame['clock'])<.15
            result['checks'].append({'check':'resumed video frame uses media clock',**frame})
            browser.close()
        result['status']='PASS'
    except Exception as exc:
        result.update(status='FAIL',exception=type(exc).__name__,message=str(exc))
        raise
    finally:
        (args.out/'browser-check.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
