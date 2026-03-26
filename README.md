# AI Coding Digest Pipeline

This repository contains a cloud-friendly scaffold for a daily AI coding digest:

- collect candidate articles from a small set of priority sources
- select and summarize them with OpenAI
- write dated Markdown outputs
- render a static site
- publish through GitHub Pages

## Repository layout

- `config/sources.json`: source registry for the collector
- `scripts/run_digest.py`: fetch candidates and ask OpenAI to build the digest
- `scripts/render_site.py`: convert Markdown into static HTML pages
- `.github/workflows/digest.yml`: daily GitHub Actions workflow
- `content/`: dated Markdown outputs
- `data/raw/`: collected candidate metadata
- `data/processed/`: model-selected digest JSON
- `site/`: static pages deployed to GitHub Pages

## How GitHub triggers the digest

For this workflow, GitHub should not try to trigger the Codex desktop app directly. The reliable cloud pattern is:

1. GitHub Actions runs on a schedule or manual dispatch.
2. The workflow executes `scripts/run_digest.py`.
3. The script performs deterministic source fetching with Python.
4. The script calls the OpenAI API to rank and summarize the candidates.
5. The workflow writes outputs back to the repo and deploys the site.

That separation matters:

- fetching should be explicit and reproducible in code
- the model should do judgment and summarization, not own the crawl loop
- GitHub Actions can run this without depending on your laptop or the Codex desktop UI

## Can GitHub trigger Codex?

Yes, but there are two different meanings:

### Recommended: use the OpenAI API directly

This repo uses the OpenAI Python SDK and the Responses API. That is the cleanest way to run model-powered digest generation inside GitHub Actions.

Relevant official sources:

- [OpenAI model catalog](https://developers.openai.com/api/docs/models)
- [GPT-5-Codex model page](https://developers.openai.com/api/docs/models/gpt-5-codex)
- [GPT-5.1-Codex model page](https://developers.openai.com/api/docs/models/gpt-5.1-codex)

### Optional: use Codex CLI inside the GitHub runner

You can also install Codex CLI in GitHub Actions and invoke it from the runner. That is closer to “triggering Codex”, but it is usually better suited to coding tasks than to deterministic news/digest pipelines.

Relevant official sources:

- [OpenAI Codex CLI getting started](https://help.openai.com/en/articles/11096431-openai-codex-ci-getting-started)
- [Introducing Codex](https://openai.com/index/introducing-codex/)

For this digest use case, the API-first approach is the better fit.

## GitHub setup

1. Create a repository for the digest.
2. Push this scaffold into that repository.
3. In GitHub, add `OPENAI_API_KEY` under Settings -> Secrets and variables -> Actions.
4. In GitHub, enable Pages and set the source to GitHub Actions.
5. Run the workflow once with `workflow_dispatch`.

After that:

- the Markdown digest will be committed into `content/`
- the JSON artifacts will land in `data/`
- the public site will be published from `site/`

## Scheduling notes

The workflow uses a cron schedule. GitHub Actions schedules run in UTC, may be delayed during high load, and should not be placed right on the hour if you want fewer collisions.

Official GitHub references:

- [Events that trigger workflows](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows)
- [Using custom workflows with GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [Using secrets in GitHub Actions](https://docs.github.com/en/actions/configuring-and-managing-workflows/creating-and-storing-encrypted-secrets)

## Next hardening steps

- improve each source parser instead of relying on generic landing-page extraction
- add retries and partial-failure reporting
- add a monthly archive page and RSS/JSON feed
- persist per-source dedupe state
- optionally add Slack or email delivery
# ai_articles
