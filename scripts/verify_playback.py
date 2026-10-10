#!/usr/bin/env python3
"""Verify native single-file playback/pause/seek with a fresh, muted browser.

Requires isolated Playwright + Chromium. Does not access an operator browser profile.
"""
from pathlib import Path
import argparse
import json
import os
import sys
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from subtitle_lab.pipeline import validate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',required=True)
    parser.add_argument('--render',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    url=urlparse(args.url)
    if url.scheme!='http' or url.hostname not in ('127.0.0.1','localhost') or url.username or url.query:
        parser.error('Use an unauthenticated loopback HTTP player URL')
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
