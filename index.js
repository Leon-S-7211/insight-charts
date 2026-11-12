// insight-charts bundle entry for DeepSeek Harness.
//
// Registers skills/insight-charts/SKILL.md as one on-demand agent skill. The skill's relative
// paths (scripts/, references/, examples/, assets/) resolve against the skill directory.
// Nothing is imported from the harness; the plugin only uses the injected `skills` service.
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

export const name = 'dsh-plugin-insight-charts'
export const inject = ['skills']

const skillDir = join(dirname(fileURLToPath(import.meta.url)), 'skills', 'insight-charts')

/** Split SKILL.md into its frontmatter description and its body (LF or CRLF). */
export function splitFrontmatter(text) {
  const open = /^---\r?\n/.exec(text)
  if (!open) return { description: undefined, body: text }
  const rest = text.slice(open[0].length)
  const close = /\r?\n---[ \t]*(?:\r?\n|$)/.exec(rest)
  if (!close) return { description: undefined, body: text }
  const meta = rest.slice(0, close.index)
  const body = rest.slice(close.index + close[0].length).replace(/^(?:[ \t]*\r?\n)+/, '')
  const match = /^description:[ \t]*(.+?)[ \t]*$/m.exec(meta)
  return { description: match?.[1]?.trim(), body }
}

export function apply(ctx) {
  const { description, body } = splitFrontmatter(readFileSync(join(skillDir, 'SKILL.md'), 'utf8'))
  ctx.effect(() =>
    ctx.skills.register({
      name: 'insight-charts',
      source: 'bundled',
      description:
        description ?? 'Draw research-report-quality charts with matplotlib in two house styles.',
      content: body,
      resourceBase: { kind: 'directory', path: skillDir },
    }),
  )
}
