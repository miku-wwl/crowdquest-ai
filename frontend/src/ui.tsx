import { useEffect, useState } from 'react';

export const WARNING = 'DEVELOPMENT PREVIEW — NOT APPROVED / NOT EXECUTED';
export type Candidate = {id: string; suggestion: string; event_time: number; state: string; source: string};
type Me = {authenticated: boolean; configured?: boolean; login?: string; csrf?: string; connection: string; reason?: string;
  eventsub?: {ready: boolean; counters: {keepalives: number; notifications: number; accepted: number}} | null};
type Pairings = {pending: string[]; ready: number};
type OverlayData = {state: string; text?: string; source?: string; expires_at?: number; remaining_seconds?: number; deadline?: number; reason?: string; code?: string};

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {credentials: 'same-origin', cache: 'no-store',
    signal: AbortSignal.timeout(5000), ...options});
  if (!response.ok) throw new Error(response.status === 401 ? 'Sign in as the channel owner to continue.' :
    response.status === 403 ? 'Request rejected. Refresh the dashboard and try again.' :
    'The operation could not be completed. Check the connection and try again.');
  return response.json();
}

export function CandidateList({candidates, selected, onSelect}: {
  candidates: Candidate[]; selected: string; onSelect: (id: string) => void;
}) {
  return <div className="candidate-list" role="radiogroup" aria-label="Viewer suggestions">
    {candidates.map(candidate => <button key={candidate.id} role="radio" aria-checked={selected === candidate.id}
      className={`candidate ${selected === candidate.id ? 'selected' : ''}`} onClick={() => onSelect(candidate.id)}>
      <span className="candidate-top"><span className="source">{candidate.source === 'synthetic' ? 'SYNTHETIC TEST DATA' : 'TWITCH EVENTSUB'}</span>
        <time>{new Date(candidate.event_time * 1000).toLocaleTimeString()}</time></span>
      <span className="suggestion">{candidate.suggestion}</span>
      <span className="candidate-bottom"><span>{candidate.state === 'previewed' ? 'Previously previewed' : 'Candidate'}</span>
        <span>{selected === candidate.id ? 'Selected ✓' : 'Select →'}</span></span>
    </button>)}
  </div>;
}

export function Dashboard() {
  const [me, setMe] = useState<Me>({authenticated: false, connection: 'checking'});
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [pairings, setPairings] = useState<Pairings>({pending: [], ready: 0});
  const [selected, setSelected] = useState('');
  const [error, setError] = useState(window.location.search.includes('auth_error') ? 'Twitch sign-in failed. Check the configured owner and granted scope.' : '');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true, working = false;
    async function refresh() {
      if (working) return;
      working = true;
      try {
        const identity = await api<Me>('/api/me');
        if (!active) return;
        setMe(identity);
        if (identity.authenticated) {
          const [items, overlays] = await Promise.all([
            api<{candidates: Candidate[]}>('/api/candidates'), api<Pairings>('/api/overlays'),
          ]);
          if (active) {setCandidates(items.candidates); setPairings(overlays);
            setError(value => value === 'Connection lost. Reconnect to the local application.' ? '' : value);}
        } else {setCandidates([]); setPairings({pending: [], ready: 0}); setSelected('');}
      } catch (e) {
        if (active) {setError('Connection lost. Reconnect to the local application.'); setCandidates([]);
          setMe({authenticated: false, connection: 'disconnected'}); setSelected('');}
      } finally {working = false;}
    }
    void refresh(); const timer = setInterval(refresh, 2000);
    return () => {active = false; clearInterval(timer);};
  }, []);
  async function mutate(path: string, body = {}) {
    setBusy(true); setError(''); setNotice('');
    try {
      await api(path, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': me.csrf || ''}, body: JSON.stringify(body)});
      setNotice(path === '/api/preview' ? 'Preview is available to paired overlays for 60 seconds.' :
        path === '/api/overlays/authorize' ? 'Overlay paired. Wait for Ready, then choose a preview.' : 'Done.');
    } catch (e) {setError((e as Error).message);} finally {setBusy(false);}
  }
  const chosen = candidates.find(c => c.id === selected);
  return <div className="shell">
    <header><a className="brand" href="/" aria-label="CrowdQuest home"><span className="brand-mark">CQ</span> CrowdQuest<span className="brand-ai">AI</span></a>
      <span className="phase">PHASE 01 <span>Connectivity lab</span></span>
      <span className={`connection ${me.eventsub?.ready ? 'live' : ''}`}><i />{me.connection.replaceAll('_', ' ')}</span></header>
    <main>
      <div className="hero"><div><p className="eyebrow">CROWD-POWERED. STREAMER-CONTROLLED.</p>
        <h1>Give chat a place to play.</h1><p className="lede">Collect suggestions. Choose what appears on your stream.</p></div>
        <div className="owner"><span>CHANNEL OWNER</span><strong>{me.login ? `@${me.login}` : 'Not connected'}</strong><small>Read-only Twitch integration</small></div></div>
      <div className="warning" role="note">{WARNING}</div>
      {me.authenticated && me.eventsub && <p className="fine" role="status">
        EventSub {me.eventsub.ready ? 'listening' : 'not ready'} · Heartbeats {me.eventsub.counters.keepalives} ·
        Notifications {me.eventsub.counters.notifications} · Stored {me.eventsub.counters.accepted}
      </p>}
      {error && <div role="alert" className="error">{error}</div>}
      {notice && <div role="status" className="notice">{notice}</div>}
      {!me.authenticated ? <section className="signin"><span className="step-number">01</span><h2>Connect your channel</h2>
        <p>Sign in with the configured broadcaster account to review suggestions and control development previews.</p>
        {me.reason === 'TWITCH_AUTH_TEMPORARILY_UNAVAILABLE' ?
          <p role="status">Twitch is temporarily unavailable. Your session is retained; retrying.</p> :
          <a className="primary" href="/auth/twitch/start">Connect Twitch →</a>}
        {me.configured === false && <p className="setup-hint">Local setup is required. Follow the Twitch setup instructions in the README.</p>}
        <p className="fine">Only chat reading is requested. This phase does not use AI or execute challenges.</p></section> :
        <div className="workspace"><section className="inbox"><div className="section-title"><h2>Audience inbox <span>{candidates.length}</span></h2><span>!quest &lt;suggestion&gt;</span></div>
          {candidates.length ? <CandidateList candidates={candidates} selected={selected} onSelect={id => {setSelected(id); setNotice('');}} /> :
            <div className="empty"><span>↳</span><h3>Waiting for your first quest</h3><p>Ask a viewer to type <code>!quest Survive 60 seconds</code> in your channel.</p><small>Nothing is displayed automatically.</small></div>}</section>
          <aside><section className="preview-panel"><p className="eyebrow">MANUAL DEVELOPMENT PREVIEW</p><h2>Your stream, your choice.</h2>
            <div className="selected-preview">{chosen ? <p>{chosen.suggestion}</p> : <p className="muted">Select a suggestion from the inbox.</p>}</div>
            <button className="primary" disabled={!chosen || busy || !pairings.ready} onClick={() => void mutate('/api/preview', {candidate_id: selected})}>Preview selected →</button>
            <button className="quiet" disabled={busy} onClick={() => void mutate('/api/preview/clear')}>Clear preview</button>
            <p className="fine">A preview is visible for 60 seconds. It is not Plan Approval, Authorization or execution.</p></section>
            <section className="overlay-panel"><div className="section-title"><h3>Browser Source</h3><span className={pairings.ready ? 'ready' : 'muted'}>{pairings.ready ? `${pairings.ready} Ready` : 'Not ready'}</span></div>
              <p>Open the overlay, match its pairing code, then allow read-only display here.</p><a href="/overlay" target="_blank" rel="noreferrer">Open development overlay ↗</a>
              <code className="url">{window.location.origin}/overlay</code>
              {pairings.pending.map(code => <button className="pair" key={code} disabled={busy} onClick={() => void mutate('/api/overlays/authorize', {code})}>Pair overlay {code}</button>)}
              <small>Refresh or reconnect clears the old preview. Only a new selection is shown.</small></section>
          </aside></div>}
      <footer><span>Suggestions are untrusted text. You stay in control.</span><span>Phase 1 · No AI / No AIG execution</span></footer>
    </main></div>;
}

export function Overlay() {
  const [data, setData] = useState<OverlayData>({state: 'connecting'});
  useEffect(() => {
    let active = true, working = false, view = crypto.randomUUID();
    async function poll() {
      if (working) return;
      working = true;
      const started = performance.now();
      try {
        const response = await fetch('/api/overlay/current', {cache: 'no-store', credentials: 'same-origin',
          headers: {'X-Overlay-View': view}, signal: AbortSignal.timeout(4000)});
        if (response.status === 401) {
          view = crypto.randomUUID();
          const pair = await api<{code: string; approved: boolean}>('/api/overlay/pair', {method: 'POST'});
          if (active) setData({state: 'pairing', code: pair.code});
        } else {
          if (!response.ok) throw new Error('OVERLAY_UNAVAILABLE');
          const value: OverlayData = await response.json();
          if (value.state === 'preview') {
            // Compatibility with the already-running Phase 1 server: use its HTTP
            // Date header, never the client's wall clock, for the legacy response.
            if (value.remaining_seconds === undefined && value.expires_at !== undefined) {
              const serverNow = Date.parse(response.headers.get('Date') || '');
              value.remaining_seconds = Math.min(60, value.expires_at - serverNow / 1000);
            }
            if (!Number.isFinite(value.remaining_seconds) || value.remaining_seconds! <= 0 || value.remaining_seconds! > 60) {
              throw new Error('INVALID_PREVIEW_DURATION');
            }
            value.deadline = started + value.remaining_seconds! * 1000;
            if (value.deadline <= performance.now()) {
              value.state = 'waiting'; value.text = undefined;
            }
          }
          if (active) setData(value);
        }
      } catch {
        view = crypto.randomUUID();
        if (active) setData({state: 'disconnected'});
      } finally {working = false;}
    }
    void poll(); const timer = setInterval(poll, 1000);
    const expiry = setInterval(() => setData(value => value.deadline !== undefined && value.deadline <= performance.now() ? {state: 'waiting', reason: 'PREVIEW_ENDED'} : value), 250);
    return () => {active = false; clearInterval(timer); clearInterval(expiry);};
  }, []);
  return <main className="overlay-shell"><div className="overlay-card"><div className="overlay-brand"><span className="brand-mark">CQ</span> CrowdQuest AI <span>LIVE PREVIEW LAB</span></div>
    <div className="warning">{WARNING}</div>
    {data.state === 'preview' ? <><p className="eyebrow">{data.source === 'synthetic' ? 'SYNTHETIC TEST DATA' : 'STREAMER-SELECTED SUGGESTION'}</p>
      <h1 className="overlay-text">{data.text}</h1><p className="fine">Temporary display preview · No challenge has been executed</p></> :
      <div className="overlay-empty"><p className="eyebrow">{data.state.toUpperCase()}</p><h1>{data.state === 'pairing' ? 'Pair this Browser Source' : data.state === 'disconnected' ? 'Connection lost' : data.state === 'expired' ? 'Preview expired' : 'Ready for your next idea'}</h1>
        <p>{data.state === 'pairing' ? 'Match this code in the owner dashboard:' : 'Waiting for a new, deliberate streamer selection.'}</p>
        {data.code && <strong className="pair-code">{data.code}</strong>}</div>}
    <div className="overlay-footer">READ-ONLY DISPLAY <span>PHASE 01</span></div></div></main>;
}
