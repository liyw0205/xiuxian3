# 灵果凑十

洞天福地小游戏改造版。

- 入口：`static/dongtian/lingguo-sum-ten/index.html`
- 后端：`GET/POST /xiuxian/dongtian/lingguo-sum-ten/*`
- 规则：框选矩形，数字合计为 10 时消除得分。
- 难度：每局由服务端随机决定，前端不提供模式选择。
- 结算：2 分 30 秒到时自动向后端提交 `score`、`cleared_cells`、`valid_clears`、`elapsed_seconds` 和单局凭证，后端签发洞天兑换码。

源码只保留修仙接入需要的游戏本体、构建配置和运行素材。
