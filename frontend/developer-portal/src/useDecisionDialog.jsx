import { useEffect, useId, useRef, useState } from 'react';

// Keep confirmations and metadata editing inside the portal, with visible, testable controls.
export function useDecisionDialog() {
  const [decision, setDecision] = useState(null);
  const [value, setValue] = useState('');
  const pending = useRef(null);
  const titleId = useId();
  function finish(result) {
    const resolve = pending.current;
    pending.current = null;
    setDecision(null);
    resolve?.(result);
  }
  useEffect(() => () => { pending.current?.(null); }, []);
  function ask(message, initialValue) {
    pending.current?.(null);
    setValue(initialValue ?? '');
    setDecision({ message, editing: initialValue !== undefined });
    return new Promise(resolve => { pending.current = resolve; });
  }
  const dialog = decision && <div className="decision-overlay" onKeyDown={event => {
    if (event.key === 'Escape') { event.preventDefault(); finish(null); }
  }}>
    <section className="panel decision-dialog" role="dialog" aria-modal="true" aria-labelledby={titleId}>
      <h3 id={titleId}>{decision.message}</h3>
      <form onSubmit={event => { event.preventDefault(); finish(decision.editing ? value : true); }}>
        {decision.editing && <label>New value<input autoFocus maxLength={255} value={value} onChange={event => setValue(event.target.value)} /></label>}
        <div className="actions">
          <button type="button" className="small-button" autoFocus={!decision.editing} onClick={() => finish(null)}>Cancel</button>
          <button type="submit" className="primary">{decision.editing ? 'Save value' : 'Confirm'}</button>
        </div>
      </form>
    </section>
  </div>;
  return { confirm: message => ask(message), prompt: (message, initialValue) => ask(message, initialValue), dialog };
}
