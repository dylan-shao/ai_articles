# AI Coding Daily Digest - 2026-11-10

## Executive Summary
- 今天高信号内容集中在两类：一是代码智能从“聊天式助手”转向“为代理和人类提供代码库理解基础设施”，二是组织开始把 AI 产出的下游瓶颈从写代码转向评审与合规分流。
- Sourcegraph 宣布停止 Cody，技术方向明确转向大型代码库理解、检索与控制层，这对平台团队判断“自建代理栈需要什么底座”很有参考价值。
- 另一篇 Sourcegraph 文章更具落地性：它把 PR 审核拆成 Ship/Show/Ask 三类，并尝试用代理做路由与证据生成，直接对应 AI 编码普及后的工程流程重构。

## Selected Items

## Keeping code moving with clearer review expectations | Sourcegraph
- Source: Sourcegraph Blog
- Author: Constantin Nicolae
- Publish date: 2026-11-10
- URL: https://sourcegraph.com/blog/what-we-learned-building-a-pr-approval-bot

Sourcegraph 描述了一个内部 PR 路由实验：随着代理生成更多代码，真正的瓶颈转移到评审阶段，因此他们引入基于 Ship/Show/Ask 的分类体系，让代理先阅读 diff 和上下文，再给出需要“可直接合并、合并后展示、合并前必须询问”的建议与证据。

Why it matters: 这不是泛泛而谈的“AI 改变开发”，而是工程组织层面的具体控制面设计：当代码生成提速后，评审、审批和上下文切换会成为新瓶颈。对平台/后端负责人来说，这篇文章提供了一个可复制的最小流程改造模板：先做风险分流，再把人的注意力集中在高风险变更上。

Key takeaways:
- Ship/Show/Ask 把单一“必须审批”规则拆成不同风险路径，更适合 AI 时代的高吞吐变更流。
- 代理的价值不只是给出结论，而是读取 diff 与周边代码后提供可审计证据，帮助团队逐步建立自动路由信任。

Tags: code-review, workflow-automation, ai-coding-agents, engineering-process
Scores: signal 9/5, novelty 8/5, actionability 9/5

## Sunsetting Sourcegraph Cody and building the future of code intelligence | Sourcegraph
- Source: Sourcegraph Blog
- Author: Dan Adler
- Publish date: 2026-11-09
- URL: https://sourcegraph.com/blog/sunsetting-cody-future-of-code-intelligence

Sourcegraph 宣布 Cody 将于 2027-01-31 停止服务，并坦承自己两年前没有把 Cody 演进为编码代理，因此决定退出“通用 AI 编码助手”竞争，转而专注于其更有优势的方向：复杂代码库理解、检索与为开发者及其所选代理提供清晰度和控制力。

Why it matters: 高信号点不在于产品下线本身，而在于一个早期代码智能公司对价值层的重新判断：在代理主导的时代，长期壁垒可能不是“再做一个助手 UI”，而是代码库索引、语义理解、权限边界、上下文供应和治理能力。这对企业内部自建 AI 编码平台的架构分层很重要。

Key takeaways:
- Sourcegraph 公开承认 standalone coding assistant 市场已被代理范式重构，代码智能底座比助手前端更具长期价值。
- 企业团队应把注意力放到“如何给任意代理稳定、安全地提供代码库上下文”这一中间层，而不是绑定某个单一助手产品。

Tags: repo-understanding, code-intelligence, platform-strategy, ai-coding-agents
Scores: signal 8/5, novelty 7/5, actionability 7/5

## Top Items

- Keeping code moving with clearer review expectations | Sourcegraph
- Sunsetting Sourcegraph Cody and building the future of code intelligence | Sourcegraph

## New Terms

- Ship/Show/Ask 评审分流
- 代码智能底座
- 评审路由代理

## Themes

- AI 编码的瓶颈从生成转向评审与治理
- 代码助手竞争转向代码库理解与上下文基础设施

## Implications

- 平台团队应优先建设代码库索引、权限控制、上下文检索和可审计证据链，而不是只评估模型前端体验。
- 工程管理层应重新设计代码评审政策，把变更按风险分流，并允许 AI 在低风险路径承担预审与路由职责。

## Recommended Reading Order

- Sunsetting Sourcegraph Cody and building the future of code intelligence | Sourcegraph
- Keeping code moving with clearer review expectations | Sourcegraph

## What to Ignore

- GitHub Copilot 新增 Claude Fable 5.2 主要是模型可用性与计费/保留策略更新，缺少方法、评测或系统设计细节。
- 不要把一般性的模型上新当作工程流程创新；今天更值得关注的是代码智能分层和评审控制面。

## Sources Checked

- [Sourcegraph Blog](https://sourcegraph.com/blog)
- [Sourcegraph Blog](https://sourcegraph.com/blog)
- [GitHub Changelog](https://github.blog/changelog/)
