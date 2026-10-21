function(el, x, data) {
  // Keep shared-coordinate bubbles, but expose every facility they contain.
  const old = document.getElementById(el.id + '-details');
  if (old) old.remove();
  const panel = document.createElement('section');
  panel.id = el.id + '-details';
  panel.className = 'followup-details';
  panel.setAttribute('aria-label', 'Restaurant inspection details');
  const instruction = document.createElement('p');
  instruction.textContent = 'Hover to preview restaurants. Click a bubble for all its facilities, or choose a restaurant below. Bubble area represents facility count; drag to zoom and double-click to reset.';
  panel.appendChild(instruction);
  const label = document.createElement('label');
  label.htmlFor = el.id + '-restaurant';
  label.textContent = 'Choose a restaurant: ';
  const select = document.createElement('select');
  select.id = label.htmlFor;
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = 'Select a facility and inspection date';
  select.appendChild(placeholder);
  data.records.forEach((record, index) => {
    const option = document.createElement('option');
    option.value = String(index);
    option.textContent = record.name + ' | ' + record.initial_date;
    select.appendChild(option);
  });
  panel.append(label, select);
  const results = document.createElement('div');
  results.className = 'followup-results';
  results.setAttribute('aria-live', 'polite');
  panel.appendChild(results);
  el.after(panel);

  function reportLink(url, encounter, visit) {
    const link = document.createElement('a');
    // Accela exports may link to its search portal rather than a specific PDF.
    if (typeof url !== 'string' || !/^https?:\/\//i.test(url)) {
      const unavailable = document.createElement('span');
      unavailable.textContent = visit + ' report unavailable (' + encounter + ')';
      return unavailable;
    }
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    const portal = url.includes('/Cap/CapHome.aspx');
    link.textContent = visit + (portal ? ' report search' : ' report') + ' (' + encounter + ')';
    return link;
  }

  function show(records) {
    results.replaceChildren();
    const summary = document.createElement('p');
    summary.textContent = records.length + (records.length === 1 ? ' facility selected' : ' facilities at this coordinate');
    results.appendChild(summary);
    records.forEach(record => {
      const card = document.createElement('article');
      const heading = document.createElement('h4');
      heading.textContent = record.name;
      const detail = document.createElement('p');
      detail.textContent = 'Initial / Comprehensive: ' + record.initial_date + ' (score ' + record.initial_score +
        ') → ' + record.purpose + ': ' + record.followup_date + ' (score ' + record.followup_score +
        '), ' + record.days + ' days later. Facility ID: ' + record.id;
      card.append(heading, detail, reportLink(record.initial_report, record.initial_encounter, 'Initial'),
        document.createTextNode(' · '), reportLink(record.followup_report, record.followup_encounter, 'Follow-up'));
      results.appendChild(card);
    });
  }
  select.addEventListener('change', () => {
    if (select.value === '') results.replaceChildren();
    else show([data.records[Number(select.value)]]);
  });
  el.on('plotly_click', event => {
    const key = event.points[0].customdata;
    const matches = data.records.filter(record => record.key === key);
    if (!matches.length) return;
    select.value = '';
    show(matches);
  });
}
