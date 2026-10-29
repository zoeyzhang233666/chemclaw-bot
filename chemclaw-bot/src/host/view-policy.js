export const VIEW_POLICY = [
  'Conversational visualization: for business answers, give the conclusion and the corresponding inline view whenever any condition below applies. Decide from the shape of the answer, never from whether the user explicitly requested a chart. Honor an explicit request for text only or no charts.',
  '- At least two numeric indicators answering what the current level is, whether it is expensive, or whether it is acceptable: metric cards, normally two to four.',
  '- One object with at least three time observations: line; use area when cumulative quantity is the point.',
  '- At least two objects compared or ranked at the same time: bar; use hbar when category labels exceed six characters or there are more than eight categories.',
  '- One whole split into three to six parts, with composition or share as the question: donut.',
  '- Multi-field results with at least three rows and three columns: table.',
  '- Completeness, task progress or quota consumption is part of the conclusion: progress.',
  '- Risks, anomalies, conflicting measurement definitions or missing data need attention: callout.',
  '- Repeated conversion, cost, price-comparison or break-even calculations: an interactive calculator using inputs and formulas.',
  '- Parameters must be confirmed before execution: options, confirm or form in a supported chat.',
  'Choose one primary component for each data relationship: time axis → line/area; size comparison → bar/hbar; composition → donut; two numeric variables → scatter; a matrix → heatmap; quantified flows between stages → sankey; comparable normalized dimensions with explicit axis maxima → radar; stage conversion → funnel; many composition categories → treemap; one value against a stated maximum → gauge; multi-field detail → table; otherwise sandboxed html. Prefer the existing simple SVG chart when it expresses the answer; advanced charts load only when needed. Do not duplicate the same data in several charts. Never invent, estimate or interpolate observations to complete a chart; use null for missing points. Keep units and evidence traceable. Deliver the useful conclusion and view promptly, before optional file exports.',
].join('\n')
