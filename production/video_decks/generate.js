const fs = require('fs');
const path = require('path');
const pptxgen = require('pptxgenjs');
const html2pptx = require('/Users/zhekaili/.codex/skills/powerpoint/scripts/html2pptx.js');

const ROOT = path.resolve(__dirname, '../..');
const OUT = path.join(ROOT, 'runs/live-20261010T142614Z-b7aaa14e/package/video_decks');
const TMP = path.join(OUT, '_html');
fs.mkdirSync(TMP, { recursive: true });

// Four visual roles: warm paper, ink, teal accent, and sand accent.
// White and gray are neutral surfaces rather than additional accent hues.
const palette = {
  paper: '#F6F5F1',
  white: '#FFFFFF',
  ink: '#182433',
  teal: '#2F6F72',
  sand: '#B58A45',
  tealTint: '#E7EFEE',
  sandTint: '#F0E8DA',
  surface: '#ECEEED',
  muted: '#5D6870',
  line: '#CDD2D3',
};

const baseCss = `
  * { box-sizing: border-box; }
  html { background: ${palette.paper}; }
  body {
    width: 720pt; height: 405pt; margin: 0; padding: 0;
    display: flex; position: relative; overflow: hidden;
    background: ${palette.paper}; color: ${palette.ink};
    font-family: Arial, Helvetica, sans-serif;
  }
  h1, h2, p { margin: 0; font-family: Arial, Helvetica, sans-serif; }
  h1, h2 { font-size: 28pt; line-height: 1.08; font-weight: 600; color: ${palette.ink}; }
  p { font-size: 11pt; line-height: 1.30; color: ${palette.ink}; }
  .feature { font-size: 18pt; line-height: 1.18; font-weight: 600; }
  .lede { font-size: 18pt; line-height: 1.24; font-weight: 400; color: ${palette.muted}; }
  .label { font-size: 11pt; line-height: 1.18; letter-spacing: .8pt; font-weight: 600; color: ${palette.teal}; text-transform: uppercase; }
  .small { font-size: 11pt; line-height: 1.30; color: ${palette.muted}; }
  .topline { position:absolute; left:42pt; right:42pt; top:34pt; height:1pt; background:${palette.line}; }
  .brand { position:absolute; left:42pt; top:12pt; width:260pt; }
  .brand p, .topic p { font-size:11pt; line-height:1.24; letter-spacing:.8pt; font-weight:600; color:${palette.teal}; text-transform:uppercase; }
  .topic { position:absolute; right:42pt; top:12pt; width:210pt; text-align:right; }
  .section { position:absolute; left:42pt; top:55pt; width:636pt; }
  .section h2 { margin-top:10pt; }
  .note { position:absolute; left:42pt; bottom:38pt; width:636pt; }
  .card { background:${palette.white}; border:1pt solid ${palette.line}; border-radius:2pt; }
  .surface { background:${palette.surface}; border:1pt solid ${palette.surface}; border-radius:2pt; }
  .tint { background:${palette.tealTint}; border:1pt solid ${palette.tealTint}; border-radius:2pt; }
  .warm { background:${palette.sandTint}; border:1pt solid ${palette.sandTint}; border-radius:2pt; }
  .dark { background:${palette.ink}; border:1pt solid ${palette.ink}; border-radius:2pt; }
  .tag { background:${palette.tealTint}; border:0; border-radius:2pt; padding:8pt 5pt; text-align:center; }
  .connector { width:30pt; height:30pt; display:flex; align-items:center; justify-content:center; }
  .connector p { width:100%; font-size:28pt; line-height:1; font-weight:400; color:${palette.teal}; text-align:center; }
  .rule { height:3pt; width:28pt; background:${palette.teal}; }
`;

function shell(content, extraCss = '') {
  return `<!doctype html><html><head><meta charset="utf-8"><style>${baseCss}${extraCss}</style></head><body>${content}</body></html>`;
}

function header(topic) {
  return `
    <div class="brand"><p>Scholar in the Loop</p></div>
    <div class="topic"><p>${topic}</p></div>
    <div class="topline"></div>
  `;
}

function flowArrow() {
  return '<div class="connector"><p>→</p></div>';
}

function titleSlide(kicker, title, subtitle, stages) {
  const stageRows = stages.map((stage, i) => `
    <div style="height:61pt;padding:11pt 0;border-bottom:${i === stages.length - 1 ? '0' : '1pt'} solid rgba(255,255,255,.22);">
      <p class="label" style="color:${i === stages.length - 1 ? palette.sand : '#D8E3E2'};">${stage[0]}</p>
      <p class="feature" style="color:#FFFFFF;margin-top:5pt;">${stage[1]}</p>
    </div>`).join('');
  return shell(`
    <div style="position:absolute;left:42pt;top:50pt;width:420pt;">
      <p class="label">${kicker}</p>
      <h1 style="margin-top:16pt;">${title}</h1>
      <p class="lede" style="margin-top:24pt;width:390pt;">${subtitle}</p>
    </div>
    <div class="dark" style="position:absolute;right:0;top:0;width:210pt;height:405pt;border-radius:0;padding:44pt 24pt 30pt 24pt;">
      <div style="width:162pt;border-top:1pt solid rgba(255,255,255,.22);border-bottom:1pt solid rgba(255,255,255,.22);">${stageRows}</div>
      <div style="position:absolute;left:24pt;right:24pt;bottom:26pt;">
        <p class="small" style="color:#D8DDDF;">AI-assisted presentation<br>Evidence reviewed by Zhekai Li</p>
      </div>
    </div>
    <div style="position:absolute;left:42pt;bottom:32pt;width:300pt;"><p class="label">Scholar in the Loop</p></div>
  `);
}

function sourceSlide(topic, sources) {
  const rows = sources.map((s) => `
    <div style="display:flex;align-items:flex-start;height:51pt;border-bottom:1pt solid ${palette.line};padding:9pt 0;">
      <div style="width:18pt;padding-top:3pt;"><div class="rule" style="width:10pt;height:2pt;"></div></div>
      <div style="width:584pt;">
        <p class="feature">${s.name}</p>
        <p class="small" style="margin-top:3pt;">${s.detail}</p>
      </div>
    </div>`).join('');
  return shell(`${header(topic)}
    <div class="section">
      <p class="label">Sources and disclosure</p>
      <h2>Trace the argument, not just the presentation</h2>
      <div style="margin-top:20pt;width:610pt;">${rows}</div>
    </div>
    <div class="note"><p class="small">Full URLs and timestamps appear in the YouTube description and linked article.</p></div>
  `);
}

function fiveCards(items, finalDark = true) {
  return items.map((x, i) => {
    const dark = finalDark && i === items.length - 1;
    return `<div class="${dark ? 'dark' : 'card'}" style="width:121pt;height:150pt;padding:20pt 16pt;">
      <p class="label" style="color:${dark ? palette.sand : palette.teal};">${x[0]}</p>
      <p class="feature" style="margin-top:18pt;color:${dark ? '#FFFFFF' : palette.ink};">${x[1]}</p>
      <p class="small" style="margin-top:13pt;color:${dark ? '#D8DDDF' : palette.muted};">${x[2]}</p>
    </div>`;
  }).join('');
}

const decks = [
  {
    id: '01',
    title: 'Use AI to Expand the Search Space, Not Choose the Research Bet',
    slides: [
      titleSlide('Research strategy', 'Use AI to expand the search space—not choose the research bet', 'Speed can broaden discovery. It cannot decide which problem deserves years of attention.', [['Explore','Broaden'],['Compare','Question'],['Verify','Test'],['Commit','Author owns']]),
      shell(`${header('Research strategy')}
        <div style="position:absolute;left:42pt;top:58pt;width:252pt;">
          <p class="label">The useful asymmetry</p>
          <h2 style="margin-top:10pt;">AI generates options faster than researchers can judge them</h2>
          <p class="lede" style="margin-top:26pt;">Treat the output as a candidate space, not a ranked answer set.</p>
        </div>
        <div style="position:absolute;left:326pt;top:82pt;width:352pt;height:238pt;display:flex;align-items:center;gap:11pt;">
          <div class="card" style="width:190pt;height:232pt;padding:22pt 18pt;">
            <p class="label">Candidate space</p>
            <div style="display:flex;flex-wrap:wrap;gap:10pt;margin-top:20pt;">
              ${['Question','Mechanism','Method','Literature','Alternative','Premise'].map(t=>`<div class="tag" style="width:70pt;height:48pt;padding-top:15pt;"><p class="small" style="font-weight:600;color:${palette.ink};">${t}</p></div>`).join('')}
            </div>
          </div>
          ${flowArrow()}
          <div class="dark" style="width:110pt;height:150pt;padding:22pt 16pt;text-align:center;">
            <p class="label" style="color:${palette.sand};">Owner</p>
            <p class="feature" style="color:#FFFFFF;margin-top:16pt;">Human</p>
            <p class="small" style="color:#D8DDDF;margin-top:18pt;">Prioritizes<br>and justifies</p>
          </div>
        </div>
      `),
      shell(`${header('Research strategy')}
        <div class="section"><p class="label">A staged exploration pattern</p><h2>Survey broadly. Then follow evidence deeply.</h2></div>
        <div class="card" style="position:absolute;left:42pt;top:156pt;width:292pt;height:174pt;padding:20pt 22pt;">
          <p class="label">Breadth first</p><p class="feature" style="margin-top:15pt;">Map adjacent literatures</p>
          <p class="small" style="margin-top:12pt;">Compare questions, methods, mechanisms, and neighboring fields before narrowing.</p>
          <div style="display:flex;justify-content:space-between;margin-top:13pt;">${['Questions','Methods','Fields'].map(t=>`<div class="tag" style="width:70pt;height:30pt;padding:7pt 3pt;"><p class="small" style="font-weight:600;color:${palette.ink};">${t}</p></div>`).join('')}</div>
        </div>
        <div style="position:absolute;left:345pt;top:228pt;">${flowArrow()}</div>
        <div class="dark" style="position:absolute;right:42pt;top:156pt;width:292pt;height:174pt;padding:20pt 22pt;">
          <p class="label" style="color:#D8E3E2;">Depth first</p><p class="feature" style="color:#FFFFFF;margin-top:15pt;">Trace mechanisms and citations</p>
          <p class="small" style="color:#D8DDDF;margin-top:12pt;">Follow every decisive claim upstream until its evidence and dependencies are visible.</p>
          <div style="display:flex;gap:8pt;margin-top:10pt;">${[['Claim',62],['Source',62],['Dependency',104]].map(([t,w])=>`<div style="width:${w}pt;height:28pt;border:1pt solid #6C858A;padding:6pt 3pt;text-align:center;"><p class="small" style="font-weight:600;color:#FFFFFF;">${t}</p></div>`).join('')}</div>
        </div>
        <div class="note"><p class="small">Nature Machine Intelligence commentary · exploration architecture, not proof of correctness</p></div>
      `),
      shell(`${header('Research strategy')}
        <div class="section"><p class="label">The human boundary</p><h2>Four responsibilities do not transfer</h2></div>
        <div style="position:absolute;left:42pt;top:158pt;width:636pt;display:flex;gap:12pt;">
          ${[['Formulate','Define the scientific problem'],['Audit','Challenge model outputs'],['Reproduce','Rebuild decisive results'],['Defend','Own every material choice']].map((x,i)=>`<div class="${i===3?'dark':'card'}" style="width:150pt;height:168pt;padding:22pt 18pt;"><div class="rule" style="background:${i===3?palette.sand:palette.teal};"></div><p class="feature" style="margin-top:24pt;color:${i===3?'#FFFFFF':palette.ink};">${x[0]}</p><p class="small" style="margin-top:15pt;color:${i===3?'#D8DDDF':palette.muted};">${x[1]}</p></div>`).join('')}
        </div>
        <div class="note"><p class="small">MIT expert perspective · the researcher remains accountable for the intellectual commitment</p></div>
      `),
      shell(`${header('Research strategy')}
        <div class="section"><p class="label">Originality is a judgment</p><h2>A promising research bet must satisfy three tests</h2></div>
        <div style="position:absolute;left:42pt;top:158pt;width:636pt;display:flex;gap:12pt;">
          ${[['Significant','The problem matters beyond convenience or novelty.'],['Non-obvious','The direction adds more than a familiar pattern.'],['Testable','Evidence can weaken the claim, not only support it.']].map(x=>`<div class="card" style="width:204pt;height:120pt;padding:22pt 20pt;"><div class="rule"></div><p class="feature" style="margin-top:17pt;">${x[0]}</p><p class="small" style="margin-top:12pt;">${x[1]}</p></div>`).join('')}
        </div>
        <div class="dark" style="position:absolute;left:42pt;right:42pt;top:277pt;height:62pt;padding:17pt 22pt;display:flex;align-items:center;">
          <p class="feature" style="color:#FFFFFF;width:100%;text-align:center;">Researcher judgment integrates significance, originality, and feasibility.</p>
        </div>
      `),
      shell(`${header('Research strategy')}
        <div class="section"><p class="label">Why verification scales poorly</p><h2>One local error can travel through a dependency graph</h2></div>
        <div style="position:absolute;left:54pt;top:166pt;width:612pt;height:118pt;display:flex;align-items:center;gap:14pt;">
          <div class="warm" style="width:158pt;height:104pt;padding:21pt 19pt;"><p class="label" style="color:${palette.sand};">Assumption</p><p class="feature" style="margin-top:15pt;">Sign error</p></div>
          ${flowArrow()}
          <div class="card" style="width:176pt;height:104pt;padding:21pt 19pt;"><p class="label">Manuscript A</p><p class="feature" style="margin-top:15pt;">Argument invalidated</p></div>
          ${flowArrow()}
          <div class="dark" style="width:176pt;height:118pt;padding:21pt 19pt;"><p class="label" style="color:#D8E3E2;">Dependent work</p><p class="feature" style="color:#FFFFFF;margin-top:14pt;">B affected<br>C affected</p></div>
        </div>
        <div class="note"><p class="small">Retraction Watch report · illustrates propagation, not a general failure rate</p></div>
      `),
      shell(`${header('Research strategy')}
        <div class="section"><p class="label">The decision gate</p><h2>Before committing, answer five questions in your own words</h2></div>
        <div style="position:absolute;left:42pt;top:160pt;width:636pt;display:flex;gap:8pt;">${fiveCards([
          ['Problem','Define it','What is being explained?'],['Importance','Justify it','Why does it matter?'],['Originality','Show novelty','What is non-obvious?'],['Evidence','Test it','What must be true?'],['Falsifier','Challenge it','What would weaken it?']
        ])}</div>
        <div class="note"><p class="feature" style="color:${palette.teal};">Many candidates enter. One researcher-justified bet exits.</p></div>
      `),
      sourceSlide('Research strategy', [
        {name:'Nature Machine Intelligence',detail:'Evidence exploration commentary · breadth-first and depth-first search'},
        {name:'MIT News',detail:'Expert perspective · formulation, auditing, reproduction, and defense'},
        {name:'Latent Space',detail:'Practitioner testimony · academia and high-risk research bets'},
        {name:'Retraction Watch',detail:'Reported case · error propagation across dependent manuscripts'},
      ]),
    ],
  },
  {
    id: '02',
    title: 'Fluent Reasoning Is Not Provenance: Build a Verification Layer',
    slides: [
      titleSlide('Evidence discipline', 'Fluent reasoning is not provenance', 'A polished answer can be readable, traceable, and still wrong. Build a verification layer.', [['Fluent','Readable'],['Traceable','Source located'],['Verified','Supported'],['Decision','Author owns']]),
      shell(`${header('Evidence discipline')}
        <div class="section"><p class="label">Three different questions</p><h2>Do not collapse fluency, provenance, and verification</h2></div>
        <div style="position:absolute;left:42pt;top:160pt;width:636pt;display:flex;gap:12pt;">
          ${[['Fluency','Can I follow the explanation?','Readable'],['Provenance','Can I locate the source?','Traceable'],['Verification','Does the evidence support the claim?','Defensible']].map((x,i)=>`<div class="${i===2?'dark':'card'}" style="width:204pt;height:164pt;padding:23pt 20pt;"><p class="label" style="color:${i===2?palette.sand:palette.teal};">${x[0]}</p><p class="feature" style="margin-top:22pt;color:${i===2?'#FFFFFF':palette.ink};">${x[1]}</p><p class="small" style="margin-top:16pt;color:${i===2?'#D8DDDF':palette.muted};">${x[2]}</p></div>`).join('')}
        </div>
        <div class="note"><p class="small">Each layer helps. Only verification earns evidentiary credit.</p></div>
      `),
      shell(`${header('Evidence discipline')}
        <div class="section"><p class="label">Reasoning tokens</p><h2>Contribution is not faithful explanation</h2></div>
        <div style="position:absolute;left:66pt;top:160pt;width:588pt;height:104pt;display:flex;align-items:center;gap:14pt;">
          <div class="tint" style="width:150pt;height:96pt;padding:22pt 18pt;text-align:center;"><p class="label">Input</p><p class="feature" style="margin-top:15pt;">Reasoning tokens</p></div>
          ${flowArrow()}
          <div class="dark" style="width:150pt;height:96pt;padding:35pt 18pt;text-align:center;"><p class="feature" style="color:#FFFFFF;">Model</p></div>
          ${flowArrow()}
          <div class="warm" style="width:150pt;height:96pt;padding:35pt 18pt;text-align:center;"><p class="feature">Answer</p></div>
        </div>
        <div class="surface" style="position:absolute;left:176pt;top:280pt;width:368pt;height:60pt;padding:13pt 20pt;text-align:center;"><p class="feature" style="color:${palette.teal};">Coherence does not prove faithful explanation.</p></div>
        <div class="note"><p class="small">Nature Machine Intelligence Perspective · conceptual analysis</p></div>
      `),
      shell(`${header('Evidence discipline')}
        <div class="section"><p class="label">Two separate checks</p><h2>A located source is not yet supporting evidence</h2></div>
        <div style="position:absolute;left:72pt;top:162pt;width:576pt;height:142pt;display:flex;align-items:center;gap:20pt;">
          <div class="card" style="width:198pt;height:136pt;padding:23pt 21pt;"><p class="label">Claim</p><p class="feature" style="margin-top:17pt;">“The method improves reliability.”</p></div>
          ${flowArrow()}
          <div style="width:328pt;height:136pt;">
            <div class="tint" style="height:60pt;padding:18pt 21pt;"><p class="feature">Source located</p></div>
            <div class="warm" style="height:60pt;margin-top:16pt;padding:18pt 21pt;"><p class="feature">Claim support still untested</p></div>
          </div>
        </div>
        <div class="note"><p class="small">Check method, context, qualifications, and scope, not just the URL.</p></div>
      `),
      shell(`${header('Evidence discipline')}
        <div class="section"><p class="label">Dependency tracing</p><h2>Verification must travel upstream</h2></div>
        <div style="position:absolute;left:54pt;top:164pt;width:612pt;height:120pt;display:flex;align-items:center;gap:14pt;">
          <div class="warm" style="width:166pt;height:108pt;padding:21pt 19pt;"><p class="label" style="color:${palette.sand};">Unverified result</p><p class="feature" style="margin-top:15pt;">Foundation</p></div>
          ${flowArrow()}
          <div class="card" style="width:176pt;height:108pt;padding:21pt 19pt;"><p class="label">Source checked</p><p class="feature" style="margin-top:15pt;">Derived work</p></div>
          ${flowArrow()}
          <div class="dark" style="width:176pt;height:122pt;padding:21pt 19pt;"><p class="label" style="color:#D8E3E2;">Dependent claims</p><p class="feature" style="color:#FFFFFF;margin-top:14pt;">C reproduced<br>D unverified</p></div>
        </div>
        <div class="note"><p class="small">Retraction Watch report · one sign error affected three dependent manuscripts</p></div>
      `),
      shell(`${header('Evidence discipline')}
        <div class="section"><p class="label">Calibration before trust</p><h2>Confidence should be tested against observed outcomes</h2></div>
        <div style="position:absolute;left:42pt;top:158pt;width:636pt;display:flex;gap:14pt;">
          <div class="card" style="width:311pt;height:150pt;padding:22pt 21pt;">
            <p class="label">Check the claim</p><p class="feature" style="margin-top:16pt;">Is the evidence traceable and relevant?</p>
            <div style="margin-top:12pt;border-top:1pt solid ${palette.line};padding-top:8pt;"><p class="small">Sources · quotations · decisive steps</p></div>
          </div>
          <div class="dark" style="width:311pt;height:150pt;padding:22pt 21pt;">
            <p class="label" style="color:${palette.sand};">Test the confidence</p><p class="feature" style="margin-top:16pt;color:#FFFFFF;">Do stated expectations match results?</p>
            <div style="margin-top:12pt;border-top:1pt solid #56636B;padding-top:8pt;"><p class="small" style="color:#D8DDDF;">Predictions · failures · updated reliance</p></div>
          </div>
        </div>
        <div class="surface" style="position:absolute;left:42pt;right:42pt;top:309pt;height:44pt;padding:12pt 20pt;text-align:center;"><p class="feature" style="color:${palette.teal};">Confidence earns trust only when it tracks performance.</p></div>
      `),
      shell(`${header('Evidence discipline')}
        <div class="section"><p class="label">The verification layer</p><h2>Five gates between a fluent draft and an author-verified claim</h2></div>
        <div style="position:absolute;left:42pt;top:160pt;width:636pt;display:flex;gap:8pt;">${fiveCards([
          ['Open','Read it','Original source'],['Align','Compare it','Claim and evidence'],['Reproduce','Rebuild it','Decisive steps'],['Trace','Follow it','Dependencies'],['Calibrate','Test it','Against outcomes']
        ])}</div>
        <div class="note"><p class="feature" style="color:${palette.teal};">Reasoning is a candidate. Citations are leads. Confidence must be calibrated.</p></div>
      `),
      sourceSlide('Evidence discipline', [
        {name:'Nature Machine Intelligence',detail:'Perspective on reasoning tokens · commentary on provenance and validity'},
        {name:'Retraction Watch',detail:'Reported dependency failure in AI-associated mathematics manuscripts'},
        {name:'SciSpace',detail:'Commercial webinar testimony · statement and reference checking'},
        {name:'Latent Space',detail:'Expert panel testimony · calibration and behavioral characterization'},
      ]),
    ],
  },
  {
    id: '03',
    title: 'Preserve Responsibility by Recording the Research Process',
    slides: [
      titleSlide('Research governance', 'Preserve responsibility by recording the process', 'Disclosure says AI was used. A process record shows what happened and who made the consequential decisions.', [['Search','Mapped'],['Evidence','Accepted'],['Analysis','Verified'],['Decision','Author owned']]),
      shell(`${header('Research governance')}
        <div class="section"><p class="label">Disclosure is not lineage</p><h2>Responsibility requires an inspectable chain of decisions</h2></div>
        <div style="position:absolute;left:42pt;top:160pt;width:636pt;display:flex;gap:12pt;">
          ${[['AI used','A label','warm'],['Tasks bounded','Who did what','card'],['Outputs checked','What entered','card'],['Claims defended','Author accountable','dark']].map(x=>`<div class="${x[2]}" style="width:150pt;height:154pt;padding:22pt 18pt;"><div class="rule" style="background:${x[2]==='dark'?palette.sand:palette.teal};"></div><p class="feature" style="margin-top:22pt;color:${x[2]==='dark'?'#FFFFFF':palette.ink};">${x[0]}</p><p class="small" style="margin-top:14pt;color:${x[2]==='dark'?'#D8DDDF':palette.muted};">${x[1]}</p></div>`).join('')}
        </div>
        <div class="note"><p class="small">MIT expert perspective · contribution and intellectual responsibility must remain visible</p></div>
      `),
      shell(`${header('Research governance')}
        <div class="section"><p class="label">Bound the division of labor</p><h2>Delegate operations. Retain scientific judgment.</h2></div>
        <div class="tint" style="position:absolute;left:42pt;top:158pt;width:311pt;height:174pt;padding:23pt 22pt;">
          <p class="label">AI-assisted · reversible</p>
          ${['Search terms','Abstract clustering','Formatting notes','Outline proposals'].map((t,i)=>`<div style="display:flex;align-items:center;margin-top:${i===0?19:11}pt;"><div style="width:18pt;height:2pt;background:${palette.teal};margin-right:12pt;"></div><p class="small" style="font-weight:600;color:${palette.ink};">${t}</p></div>`).join('')}
        </div>
        <div class="dark" style="position:absolute;right:42pt;top:158pt;width:311pt;height:174pt;padding:23pt 22pt;">
          <p class="label" style="color:${palette.sand};">Researcher · accountable</p>
          ${['Problem formulation','Evidence acceptance','Analysis and interpretation','Final claims'].map((t,i)=>`<div style="display:flex;align-items:center;margin-top:${i===0?19:11}pt;"><div style="width:18pt;height:2pt;background:${palette.sand};margin-right:12pt;"></div><p class="small" style="font-weight:600;color:#FFFFFF;">${t}</p></div>`).join('')}
        </div>
        <div class="note"><p class="small">SciSpace practitioner testimony · a useful boundary, not product validation</p></div>
      `),
      shell(`${header('Research governance')}
        <div class="section"><p class="label">Record the process, not only the result</p><h2>Negative paths explain how the final path emerged</h2></div>
        <div style="position:absolute;left:48pt;top:164pt;width:624pt;height:110pt;display:flex;align-items:center;gap:6pt;">
          ${[['Search','Tested','card'],['Interpret','Rejected','warm'],['Calculation','Revised','card'],['Claim','Accepted','dark']].map((x,i)=>`<div class="${x[2]}" style="width:132pt;height:104pt;padding:19pt 16pt;"><p class="label" style="color:${x[2]==='dark'?palette.sand:palette.teal};">${x[0]}</p><p class="feature" style="margin-top:14pt;color:${x[2]==='dark'?'#FFFFFF':palette.ink};">${x[1]}</p></div>${i<3?'<div class="connector" style="width:20pt;"><p>→</p></div>':''}`).join('')}
        </div>
        <div class="note"><p class="small">Periodic Labs founder testimony · process evidence, not independent performance validation</p></div>
      `),
      shell(`${header('Research governance')}
        <div class="section"><p class="label">Correction requires lineage</p><h2>An audit is useful only if affected claims can be located</h2></div>
        <div style="position:absolute;left:48pt;top:166pt;width:624pt;height:140pt;display:flex;align-items:center;gap:6pt;">
          ${[['Audit','Error found','card'],['Trace','Affected work','card'],['Revise','Repair where possible','warm'],['Withdraw','Remove if not fixable','dark']].map((x,i)=>`<div class="${x[2]}" style="width:132pt;height:132pt;padding:18pt 16pt;"><p class="label" style="color:${x[2]==='dark'?palette.sand:palette.teal};">${x[0]}</p><p class="feature" style="margin-top:12pt;color:${x[2]==='dark'?'#FFFFFF':palette.ink};">${x[1]}</p></div>${i<3?'<div class="connector" style="width:20pt;"><p>→</p></div>':''}`).join('')}
        </div>
        <div class="note"><p class="small">A record supports correction. It does not guarantee correctness.</p></div>
      `),
      shell(`${header('Research governance')}
        <div class="section"><p class="label">A reusable seven-field log</p><h2>Capture enough context to reconstruct the decision</h2></div>
        <div style="position:absolute;left:42pt;top:172pt;width:636pt;display:flex;flex-wrap:wrap;gap:10pt;">
          ${['Date','Task','Tool or model','Input limits'].map(x=>`<div class="card" style="width:151pt;height:76pt;padding:20pt 17pt;"><p class="feature">${x}</p></div>`).join('')}
          ${['Output used','Verification','Author decision'].map((x,i)=>`<div class="${i===2?'dark':'card'}" style="width:205pt;height:76pt;padding:20pt 17pt;"><p class="feature" style="color:${i===2?'#FFFFFF':palette.ink};">${x}</p></div>`).join('')}
        </div>
      `),
      shell(`${header('Research governance')}
        <div style="position:absolute;left:42pt;top:59pt;width:258pt;">
          <p class="label">Two records, two audiences</p><h2 style="margin-top:10pt;">Internal lineage is richer than public disclosure</h2>
          <p class="lede" style="margin-top:24pt;">Follow journal, university, funder, disciplinary, privacy, ethics, IRB, and IP requirements.</p>
        </div>
        <div style="position:absolute;right:42pt;top:68pt;width:348pt;height:274pt;">
          <div class="card" style="height:130pt;padding:18pt 22pt;"><p class="label">Internal process log</p><p class="feature" style="margin-top:10pt;">Detailed decision lineage</p><p class="small" style="margin-top:8pt;">Prompts, evidence, failed paths, verification, corrections, and decisions</p></div>
          <div class="dark" style="height:130pt;margin-top:14pt;padding:18pt 22pt;"><p class="label" style="color:${palette.sand};">Public disclosure</p><p class="feature" style="color:#FFFFFF;margin-top:10pt;">Material assistance, stated proportionally</p><p class="small" style="color:#D8DDDF;margin-top:8pt;">Audience-facing and policy-specific</p></div>
        </div>
      `),
      sourceSlide('Research governance', [
        {name:'MIT News',detail:'Expert perspective · contribution and intellectual responsibility'},
        {name:'Latent Space / Periodic Labs',detail:'Founder testimony · process lineage and negative results'},
        {name:'SciSpace',detail:'Practitioner and reviewer testimony · task boundaries, privacy, ethics, and IRB'},
        {name:'Retraction Watch',detail:'Reported case · audit, revision, and withdrawal'},
      ]),
    ],
  },
];

async function buildDeck(deck) {
  const pptx = new pptxgen();
  pptx.defineLayout({ name: 'CUSTOM_16X9', width: 10, height: 5.625 });
  pptx.layout = 'CUSTOM_16X9';
  pptx.author = 'Zhekai Li';
  pptx.subject = 'Scholar in the Loop audience video visual deck';
  pptx.title = deck.title;
  pptx.company = 'Scholar in the Loop';
  pptx.lang = 'en-US';
  pptx.theme = { headFontFace: 'Arial', bodyFontFace: 'Arial', lang: 'en-US' };

  const deckTmp = path.join(TMP, deck.id);
  fs.mkdirSync(deckTmp, { recursive: true });
  for (let i = 0; i < deck.slides.length; i += 1) {
    const htmlPath = path.join(deckTmp, `${String(i + 1).padStart(2, '0')}.html`);
    fs.writeFileSync(htmlPath, deck.slides[i], 'utf8');
    await html2pptx(htmlPath, pptx, { tmpDir: deckTmp });
  }

  const outPath = path.join(OUT, `${deck.id}-scholar-in-the-loop-final-v4.pptx`);
  await pptx.writeFile({ fileName: outPath });
  return outPath;
}

(async () => {
  const outputs = [];
  for (const deck of decks) outputs.push(await buildDeck(deck));
  fs.writeFileSync(path.join(OUT, 'deck_manifest_v4.json'), JSON.stringify({
    generated_at: new Date().toISOString(),
    design: {
      aspect_ratio: '16:9',
      reference_system: 'IBM Carbon-inspired enterprise research layout',
      style: 'academic editorial + restrained consulting presentation',
      font_family: 'Arial',
      font_sizes_pt: [28, 18, 11],
      palette,
      safeguards: [
        '42pt safe margins',
        'no video or piece numbering in audience-facing slides',
        'four visual color roles plus neutral gray',
        'flat components without decorative shadows',
        'consistent 20–24pt card padding',
        'three-level typography only',
        'at least 16pt between a two-line title and the content region',
        'container rows retain conversion-safe horizontal and vertical slack',
        'no coordinate charts without interpretable data',
        'no internal claim IDs in audience-facing slides',
      ],
    },
    decks: decks.map((d, i) => ({ title: d.title, slide_count: d.slides.length, path: outputs[i] })),
  }, null, 2));
  process.stdout.write(`${outputs.join('\n')}\n`);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
