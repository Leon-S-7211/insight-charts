// Loads the DSH entry against a stub `skills` service and checks what gets registered.
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import * as plugin from '../index.js'

const seen = []
const ctx = {
  effect: (fn) => fn(),
  skills: { register: (def) => { seen.push(def); return () => {} } },
}
plugin.apply(ctx)
const s = seen[0]
const fail = (m) => { console.error('FAIL', m); process.exit(1) }
if (seen.length !== 1) fail('expected exactly one skill')
if (s.name !== 'insight-charts') fail('wrong skill name')
if (!s.description || s.description.length < 80) fail('description not read from frontmatter')
if (s.content.startsWith('---')) fail('frontmatter not stripped')
for (const f of ['SKILL.md', 'scripts/insight_charts.py', 'references/recipes.md', 'examples/trend_events.json']) {
  if (!existsSync(join(s.resourceBase.path, f))) fail('missing ' + f)
}
console.log('ok:', s.name, '| description', s.description.length, 'chars | body', s.content.length, 'chars')
