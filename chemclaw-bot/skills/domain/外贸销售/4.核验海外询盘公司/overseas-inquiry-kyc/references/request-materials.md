# 索取资料与话术（Request Materials）

## 一、索取优先级：按"能否独立证明主体"排序

| 优先级 | 判据 | 典型材料 | 拿到后能做什么 |
|---|---|---|---|
| **P0** | 能**独立**证明主体存在与身份 | 登记号 / NIB / 营业执照 / 公司章程公证件 / 官网 Contact 页 / 公司总机 | 决定"能不能报价" |
| **P1** | 决定**怎么**交易 | 经营范围分类、产能与熔炼数据、合同主体与收货人一致性、收款账户户名、进口资质 | 决定"怎么报价、怎么签、怎么收钱" |
| **P2** | 影响交易**质量** | 技术问卷、品牌偏好、检测报告、验厂安排 | 报价后补 |

> 一次只发 P0，不要 12 条一起要。对方会觉得被审问，反而拖慢。

## 二、常见的 P0 材料清单（按国家替换名称）

| 要什么 | 中国（内贸对海外） | 印尼 | 印度 | 越南 | 巴西 |
|---|---|---|---|---|---|
| 唯一登记号 | — | NIB（13 位）+ AHU 登记号 | CIN（21 位） | MST（税号） | CNPJ（14 位） |
| 登记证明 | 营业执照 | AKTA + SK Kemenkumham | Certificate of Incorporation | Giấy chứng nhận ĐKDN | Contrato Social |
| 经营范围分类 | — | KBLI 明细 | NIC / business activity | Ngành nghề kinh doanh | CNAE |
| 税务号 | 统一社会信用代码 | NPWP | GSTIN / PAN | MST | CNPJ |
| 进口资质 | — | API-U / customs ID | IEC | — | REX / RADAR |
| 官网 Contact 页 | 官网 | 官网 | 官网 | 官网 | 官网 |
| 公司总机 | 座机 | 座机（+62 21 / 31 …） | 座机 | 座机 | 座机（+55 11 …） |

## 三、话术骨架（五段式）

每一封索取信都按这五段写，语气从"欢迎"到"流程"再到"承诺"：

```
1. 欢迎与感谢（确认收到了询盘，说明会准备报价）
2. 流程性说明（"所有新客户的标准入档流程" —— 把要求变成制度，而不是质疑）
3. 具体清单（编号列出，说明敏感信息可以打码）
4. 给替代路径（NDA 可以签、可以并行、可以由我方出模板）
5. 明确承诺（拿到 X 后 N 个工作日出报价）
```

### 关键句式（英文）

**把要求制度化的写法**：
> "To open the price file in our system, our compliance team asks for a short set of company
> documents. These are standard for all new customers, and sensitive numbers may be redacted."

**给对方台阶的写法**：
> "We fully respect your NDA. In our experience, an NDA is best used for technical formulas and
> customer lists, while the four items above are normally shared without it."

**并行推进的写法**：
> "May I suggest that we run two tracks in parallel: we sign the NDA today, and in the meantime you
> send the NIB and AHU profile with the registration numbers redacted."

**降低抵触的写法（追问产能时）**：
> "To match the right grade and packaging to your furnaces, could you kindly share ..."

**闭环确认的写法**：
> "We have checked the following: ... Two items are still open on our side: ..."

## 四、绝对不能做的事

| 不要 | 因为 |
|---|---|
| 一上来就说"为了防范诈骗" | 冒犯对方，正常客户也会反感 |
| 索要密码、网银截图、公章照片原件 | 涉及信息安全，容易引发对方警惕，也不是核验所必需 |
| 单独索要"老板身份证" | 多数国家属个人数据保护范围，走公司文件即可 |
| 承诺"资料给了就下单" | 不成立 |
| 把 NDA 当成"要资料的前置条件"去拒绝 | NDA 本身是商业惯例，问题在**把它和证照绑定** |

## 五、资料回来之后

不是收到就完事。要做三件事：

1. **比对**：登记号是否与 AHU/OSS 命中一致；地址是否与签名档一致；董事姓名是否出现在合同主体。
2. **打码检查**：对方打码了哪些字段？关键字段（公司名、登记号末几位、地址）被打掉，说明这份文件仍不足以核验。
3. **更新状态**：把对应的 `requests[]` 在 Excel 里标为"已收到/已核实"，并回填 `checks[]` 的状态。

> 资料回来 ≠ 疑点消失。例如：NIB 显示 KBLI 只有 46651（化工批发）、没有 23111（平板玻璃制造），
> 那么"自称玻璃制造商"这一条要成**新的疑点**，而不是就此关闭。

## 六、按严重度决定"要不要发报价"

| 状况 | 动作 |
|---|---|
| P0 已闭合、无疑点 | 正常报价 |
| P0 已闭合、有 medium 疑点 | 报价 + 明确条款（L/C 或高定金），不赊销 |
| P0 未闭合 | 只发"价格有效期说明"或"意向报价（Non-binding）"，不发正式 PI |
| 有 high 疑点 | 暂停报价，先解决疑点；必要时上报风控 |
