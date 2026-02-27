# Awesome Agent Skills

Unified collection of **930+ agentic skills** for AI coding assistants: Claude Code, Cursor, Gemini CLI, Codex CLI, and more.

## Structure

```
skills/
├── anthropic-official/   # Official Anthropic skills (document creation, brand guidelines, etc.)
├── community/            # 900+ community skills from Antigravity collection
spec/                     # Agent Skills specification
template/                 # Skill template for creating new skills
```

## Sources

| Source | Skills | Description |
|--------|--------|-------------|
| [anthropics/skills](https://github.com/anthropics/skills) | 16 | Official Anthropic skills — DOCX, PDF, PPTX, XLSX, brand guidelines, communications |
| [antigravity-awesome-skills](https://github.com/sickn33/antigravity-awesome-skills) | 913 | Community collection — architecture, security, DevOps, testing, AI/ML, and more |

## Usage

### Cursor

Copy skills to `.cursor/skills/` in your project or install globally.

### Claude Code

```bash
# Reference skills directly
/skill-name help me...
```

### Gemini CLI

```bash
# Place in .gemini/skills/
```

## Categories

- **Architecture** — System design, ADRs, C4, scalable patterns
- **Business** — Growth, pricing, CRO, SEO, go-to-market
- **Data & AI** — LLM apps, RAG, agents, observability
- **Development** — Language mastery, framework patterns, code quality
- **Infrastructure** — DevOps, cloud, serverless, CI/CD
- **Security** — AppSec, pentesting, vulnerability analysis
- **Testing** — TDD, test design, QA workflows
- **Workflow** — Automation, orchestration, agents
- **Documents** — DOCX, PDF, PPTX, XLSX creation and editing

## Adding New Skills

1. Create a folder in `skills/community/your-skill-name/`
2. Add a `SKILL.md` with YAML frontmatter:

```yaml
---
name: your-skill-name
description: What this skill does
---

# Your Skill Name

Instructions for the AI agent...
```

## License

Community skills: MIT License.  
Anthropic official skills: See individual skill licenses.
