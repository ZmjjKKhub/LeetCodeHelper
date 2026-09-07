"""生成 data/topics/sliding-window/ 下的三份 YAML（problems / topic 的
section_templates / plan_default），数据源全部现取现用，可重复运行。

用法：
    uv run python scripts/build_sliding_window_catalogue.py

两个数据源，权威范围不同：

  A. 灵神题单原文（https://leetcode.cn/discuss/post/3578981/）
     —— 权威：小节结构、题目顺序、哪些题是选做。
     该页是个 Next.js 页面，正文藏在 <script id="__NEXT_DATA__"> 里的一段
     markdown 字符串中。抓取整页 HTML，解析 __NEXT_DATA__ 的 JSON，在其中
     递归查找"包含'定长滑动窗口'的最长字符串"，就是正文。

  B. LeetCode 官方接口（https://leetcode.cn/api/problems/all/）
     —— 权威：标题、难度、是否会员题。
     stat_status_pairs 每条有 stat.frontend_question_id（字符串，像
     "LCP 82" 这种非纯数字的题号——它们不属于常规编号体系，直接跳过）、
     stat.question__title、stat.question__title_slug、
     difficulty.level（1/2/3 → easy/medium/hard）、paid_only。

按题号 join。校验从严：
  - 题单里的每道（有纯数字题号的）题，必须能在接口里查到，查不到就报告
    全部缺失项并直接 raise，不生成任何文件。
  - 标题不一致只报告，不当错误处理（题单标题有时是缩写）。
  - is_premium 只认接口的 paid_only，绝不看题单正文里的"（会员题）"字样。

题单正文里 LCP / LCR / 面试题 这类前缀编号的题目，本身就不是纯数字题号，
无法塞进 Problem.lc_id（int）——这与是否会员题无关，是表结构决定的硬约束，
所以直接跳过，在报告里单独列出，不计入"缺失"也不计入"会员题"。

题单正文本身还有极少数题目在两个小节各出现一次（同一题号、同一链接，
被灵神有意归到两处），例如 438 号题同时出现在 §1.2 和 §2.4。这不是两个数据
源的分歧，是同一份正文里的重复——保留题单顺序中第一次出现的那次，丢弃后面
重复的，并在报告里列出。

正文的标题其实有四级："## " 大节、"### " 小节（带 §X.Y 编号）、部分小节下
还有一层 "#### " 四级标题（带 §X.Y.Z 编号，如 §2.1 下的 §2.1.1/§2.1.2、§2.3
下的 §2.3.1/§2.3.2/§2.3.3），以及穿插的加粗细化行（"**思维扩展**" 等）。
section 只取到 "### " 这一级——§2.1.2、§2.3.1 不会单独成为 section code，
仍然折进它们的父级 "§2.1"/"§2.3"，理由是系统里按 section 分组的地方（进度
面板、R5 规则）都是按这一级粒度设计的，拆得更细只会把它们打散，没有收益。
四级标题只用来决定 is_optional：is_optional 是三个独立作用域标记的 OR
——"### " 标题自身、"#### " 标题自身、当前作用域内出现过的加粗细化——任意
层级出现新标题都会清空它自己和更内层的标记（新 "#### " 清空加粗标记；新
"### " 连四级标记一起清空；新 "## " 三个全清空）。这条清空规则正是让
§2.3.1 下的"**思维扩展（选做）**"只覆盖 3134/3261 两题、不会一路蔓延到
§2.3.2/§2.3.3 的关键，见 parse_post 里的详细注释。

关于标题语言的一个环境限制：/api/problems/all/ 的 question__title 字段实际
按请求方 IP 做地区分流——从中国大陆访问返回中文标题，从其他地区访问（这台
机器在美国出口）返回英文标题。而 paid_only / difficulty 不受此影响。为了不
把英文标题写进这个中文刷题工具，标题额外用同一站点的 GraphQL 端点
（https://leetcode.cn/graphql/，query { question(titleSlug) { translatedTitle } }）
按 title_slug 逐题补一次中文翻译，取不到翻译（极少数极新题目还没有译文）时
落回 question__title。difficulty / paid_only 仍然只信 /api/problems/all/。
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOPIC_DIR = REPO_ROOT / "data" / "topics" / "sliding-window"

POST_URL = "https://leetcode.cn/discuss/post/3578981/"
API_URL = "https://leetcode.cn/api/problems/all/"
GRAPHQL_URL = "https://leetcode.cn/graphql/"

TRANSLATED_TITLE_QUERY = (
    "query questionTranslations($titleSlug: String!) "
    "{ question(titleSlug: $titleSlug) { translatedTitle } }"
)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)

# 中文数字 -> 大节序号，用于给「五、三指针」「六、分组循环」这两个正文里没有
# §编号的大节兜底出 "§5"/"§6"。
CN_DIGIT = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6}

MAJOR_HEADING_RE = re.compile(r"^([一二三四五六])、(.+)$")
SUBSECTION_CODE_RE = re.compile(r"^§([\d.]+)\s*(.*)$")
BOLD_LINE_RE = re.compile(r"^\*\*([^*]+?)\*\*[:：]?\s*$")
PROBLEM_LINE_RE = re.compile(
    r"^-\s*\[(?P<id>[^\].]+(?:\.\d+)*?)\.\s+(?P<title>[^\]]+)\]"
    r"\((?P<url>https://leetcode\.cn/problems/[^)]+?/?)\)"
)

OPTIONAL_KEYWORDS = ("选做", "思维扩展")

# topic.yaml::section_templates 的固定映射（题单已写好模板的小节）。
SECTION_TEMPLATES = {
    "§1": "A",
    "§2.1": "B",
    "§2.2": "C",
    "§2.3": "D",
    "§3.1": "E",
    "§3.2": "E",
    "§6": "F",
}

# 每个「会出现在排期里」（非选做）小节的复盘主题文案，原样使用。
SECTION_THEMES = {
    "§1.1": "模板 A 的「入 → 更新 → 出」三步写死；题与题的差别只在维护量是什么",
    "§2.1": "模板 B：先缩到合法再更新，更新语句在 while 外",
    "§2.2": "模板 C：合法时边更新边缩，更新语句在 while 内——这是与 §2.1 唯一的结构差异，务必刻进脑子",
    "§2.3": "模板 D：D1 关注 left 的合法性，D2 关注 left-1；恰好型 = 两个「至少」相减",
    "§3.1": "相向双指针的最简形态，先把 left < right 的边界写顺",
    "§3.2": "模板 E：前提是有序 + 单调性——移动某一端能确定地让结果变大或变小",
    "§3.3": "同向双指针：与滑窗的区别是不维护窗口量，只维护位置",
    "§3.4": "背向双指针：从中心向两端扩展",
    "§3.5": "写指针 + 读指针，O(1) 空间原地修改的核心套路",
    "§3.6": "矩阵上的双指针：把二维压成一维的走法",
    "§4.1": "两个序列各一个指针，靠比较推进",
    "§4.2": "判断子序列：贪心匹配；进阶是预处理加速多次查询",
    "§5": "三指针：固定一个，剩下两个跑相向双指针",
    "§6": "模板 F：最大价值是不需要特判最后一组；别忘了外层的 i += 1",
}

PLAN_NAME = "滑动窗口 · 全量"
PLAN_START_DATE = "2026-09-07"
PROBLEMS_PER_DAY = 5


# --------------------------------------------------------------------------
# A. 抓取并解析题单正文
# --------------------------------------------------------------------------


def fetch_post_markdown() -> str:
    req = urllib.request.Request(POST_URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8")

    m = NEXT_DATA_RE.search(html)
    if not m:
        raise RuntimeError(f"{POST_URL} 的页面里没找到 __NEXT_DATA__ script")
    payload = json.loads(m.group(1))

    best: str | None = None

    def walk(node) -> None:
        nonlocal best
        if isinstance(node, str):
            if "定长滑动窗口" in node:
                if best is None or len(node) > len(best):
                    best = node
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(payload)
    if best is None:
        raise RuntimeError("__NEXT_DATA__ 里没有找到包含「定长滑动窗口」的字符串")
    return best


@dataclass(frozen=True)
class PostProblem:
    order: int
    id_text: str
    title: str
    url: str
    section: str
    section_name: str
    is_optional: bool


@dataclass
class ParseReport:
    non_numeric_ids: list[str] = field(default_factory=list)
    duplicate_dropped: list[tuple[int, str]] = field(default_factory=list)  # (lc_id, title)


def parse_post(markdown: str, report: ParseReport) -> list[PostProblem]:
    major_name: str | None = None
    major_number: int | None = None
    section_code: str | None = None
    section_title: str | None = None

    # is_optional 是三个独立作用域的标记的 OR：
    #   section_marker    —— 当前 "### " 小节标题本身含 选做/思维扩展
    #   subsection_marker —— 当前 "#### " 四级标题本身含 选做/思维扩展
    #   bold_marker       —— 当前作用域内出现过的加粗细化（"**思维扩展**" 等）
    # 作用域规则：任意层级的新标题都会清空它自己以及更内层的标记——新
    # "#### " 清空 bold_marker；新 "### " 清空 subsection_marker 和
    # bold_marker；新 "## " 三个全清空。这正是防止 §2.3.1 下
    # "**思维扩展（选做）**" 一路蔓延到 §2.3.3 的关键：一旦遇到
    # "#### §2.3.2"，bold_marker 就被清掉了。
    # 没有关键词的加粗行、没有关键词的标题只是把自己那一层的标记显式置
    # False（标题）或保持不变（加粗行——只在命中关键词时才「置位」，不命中
    # 不算「清空」，这样才符合"加粗细化"这个动作本身就是"生效"而非"复位"的
    # 语义）。
    section_marker = False
    subsection_marker = False
    bold_marker = False

    problems: list[PostProblem] = []
    seen_ids: set[int] = set()
    order = 0

    for raw_line in markdown.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("## "):
            heading = line[3:].strip()
            m = MAJOR_HEADING_RE.match(heading)
            if m:
                major_number = CN_DIGIT[m.group(1)]
                major_name = m.group(2).strip()
            else:
                # 「## 思考」「## 关联题单」「## 算法题单」等题单结构之外的
                # 收尾大节：清空当前大节状态，后面不会再有 "- [" 题目行。
                major_number = None
                major_name = None
            section_code = None
            section_title = None
            section_marker = False
            subsection_marker = False
            bold_marker = False
            continue

        if line.startswith("#### "):
            heading = line[5:].strip()
            m = SUBSECTION_CODE_RE.match(heading)
            title = m.group(2).strip() if m else heading
            subsection_marker = any(k in title for k in OPTIONAL_KEYWORDS)
            bold_marker = False
            continue

        if line.startswith("### "):
            heading = line[4:].strip()
            m = SUBSECTION_CODE_RE.match(heading)
            if m:
                section_code = f"§{m.group(1)}"
                section_title = m.group(2).strip()
                section_marker = any(k in section_title for k in OPTIONAL_KEYWORDS)
            else:
                # 「### ⚠ 滑窗的内容到这里就结束了...」这类非小节标题：
                # 后面直到下一个 "## "/"### " 之前不会再有题目行，无需处理，
                # 但仍然是一次三级标题事件，把自己这层的标记显式清空。
                section_marker = False
            subsection_marker = False
            bold_marker = False
            continue

        bold_m = BOLD_LINE_RE.match(line)
        if bold_m:
            phrase = bold_m.group(1)
            if any(k in phrase for k in OPTIONAL_KEYWORDS):
                bold_marker = True
            continue

        prob_m = PROBLEM_LINE_RE.match(line)
        if not prob_m:
            continue  # 其余都是正文说明，跳过

        if major_name is None:
            # 理论上不会发生：题目行必然在某个大节标题之后。
            raise RuntimeError(f"题目行出现在任何大节标题之前: {line!r}")

        id_text = prob_m.group("id").strip()
        title = prob_m.group("title").strip()
        url = prob_m.group("url").strip()
        if not url.endswith("/"):
            url += "/"

        code = section_code
        if code is None:
            # 「五、三指针」「六、分组循环」正文里没有 "### §" 小节标题，
            # 用大节序号兜底成 "§5" / "§6"。
            code = f"§{major_number}"
        name = f"{major_name} · {section_title}" if section_title else major_name

        order += 1

        if not id_text.isdigit():
            report.non_numeric_ids.append(f"{id_text}. {title} ({url})")
            continue

        lc_id = int(id_text)
        if lc_id in seen_ids:
            report.duplicate_dropped.append((lc_id, title))
            continue
        seen_ids.add(lc_id)

        problems.append(
            PostProblem(
                order=order,
                id_text=id_text,
                title=title,
                url=url,
                section=code,
                section_name=name,
                is_optional=section_marker or subsection_marker or bold_marker,
            )
        )

    return problems


# --------------------------------------------------------------------------
# B. 抓取 LeetCode 官方接口
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ApiProblem:
    lc_id: int
    title: str
    slug: str
    difficulty: str
    paid_only: bool


_LEVEL_TO_DIFFICULTY = {1: "easy", 2: "medium", 3: "hard"}


def fetch_api_problems() -> tuple[dict[int, ApiProblem], int]:
    req = urllib.request.Request(API_URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    by_id: dict[int, ApiProblem] = {}
    skipped_non_numeric = 0
    for entry in payload["stat_status_pairs"]:
        stat = entry["stat"]
        fq_id = stat["frontend_question_id"]
        if not isinstance(fq_id, str) or not fq_id.isdigit():
            skipped_non_numeric += 1
            continue
        lc_id = int(fq_id)
        level = entry["difficulty"]["level"]
        by_id[lc_id] = ApiProblem(
            lc_id=lc_id,
            title=stat["question__title"],
            slug=stat["question__title_slug"],
            difficulty=_LEVEL_TO_DIFFICULTY[level],
            paid_only=bool(entry["paid_only"]),
        )
    return by_id, skipped_non_numeric


def fetch_translated_title(slug: str) -> str | None:
    """按 title_slug 查一道题的中文译名（GraphQL translatedTitle）。

    /api/problems/all/ 的 question__title 会按访问者的出口 IP 地区分流（模块
    docstring里说明过），这个查询走的是同一个站点的 GraphQL 接口，不受那个
    分流影响。极少数很新的题目还没有中文译文，此时返回 None，调用方回退到
    question__title。
    """
    body = json.dumps(
        {
            "operationName": "questionTranslations",
            "variables": {"titleSlug": slug},
            "query": TRANSLATED_TITLE_QUERY,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        GRAPHQL_URL,
        data=body,
        headers={"User-Agent": UA, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    question = payload.get("data", {}).get("question")
    if not question:
        return None
    title = question.get("translatedTitle")
    return title or None


def enrich_with_chinese_titles(
    api_by_id: dict[int, ApiProblem], needed_ids: list[int]
) -> None:
    """就地把 needed_ids 里每道题的 ApiProblem.title 换成中文译名（查得到的话）。"""
    total = len(needed_ids)
    for i, lc_id in enumerate(needed_ids, start=1):
        api = api_by_id.get(lc_id)
        if api is None:
            continue
        translated = None
        for attempt in range(3):
            try:
                translated = fetch_translated_title(api.slug)
                break
            except Exception as exc:  # noqa: BLE001 - 网络抖动重试，最终失败就回退英文标题
                if attempt == 2:
                    print(f"  警告：{lc_id} ({api.slug}) 中文标题查询失败，回退英文标题: {exc}")
                else:
                    time.sleep(0.5)
        if translated:
            api_by_id[lc_id] = ApiProblem(
                lc_id=api.lc_id,
                title=translated,
                slug=api.slug,
                difficulty=api.difficulty,
                paid_only=api.paid_only,
            )
        if i % 40 == 0 or i == total:
            print(f"  中文标题翻译进度: {i}/{total}")


# --------------------------------------------------------------------------
# 合并两个数据源
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CatalogueProblem:
    lc_id: int
    title: str
    url: str
    difficulty: str
    section: str
    section_name: str
    is_optional: bool


@dataclass
class JoinReport:
    missing_from_api: list[int] = field(default_factory=list)
    title_mismatches: list[tuple[int, str, str]] = field(default_factory=list)  # (id, post, api)
    premium_dropped: list[int] = field(default_factory=list)


def join_sources(
    post_problems: list[PostProblem], api_by_id: dict[int, ApiProblem], report: JoinReport
) -> list[CatalogueProblem]:
    for p in post_problems:
        if p.id_text.isdigit() and int(p.id_text) not in api_by_id:
            report.missing_from_api.append(int(p.id_text))
    if report.missing_from_api:
        raise RuntimeError(
            "以下题单题号在 LeetCode 接口 (/api/problems/all/) 里查不到，"
            "已停止生成，未写入任何文件："
            + ", ".join(str(i) for i in report.missing_from_api)
        )

    catalogue: list[CatalogueProblem] = []
    for p in post_problems:
        lc_id = int(p.id_text)
        api = api_by_id[lc_id]
        if api.title != p.title:
            report.title_mismatches.append((lc_id, p.title, api.title))
        if api.paid_only:
            report.premium_dropped.append(lc_id)
            continue
        catalogue.append(
            CatalogueProblem(
                lc_id=lc_id,
                title=api.title,
                url=f"https://leetcode.cn/problems/{api.slug}/",
                difficulty=api.difficulty,
                section=p.section,
                section_name=p.section_name,
                is_optional=p.is_optional,
            )
        )
    return catalogue


# --------------------------------------------------------------------------
# 写 problems.yaml
# --------------------------------------------------------------------------

PROBLEMS_HEADER = """\
# 本文件由 scripts/build_sliding_window_catalogue.py 生成，不要手改。
# 重新生成： uv run python scripts/build_sliding_window_catalogue.py
#
# 列的出处：
#   title / url / difficulty  —— 取自 LeetCode 官方接口（/api/problems/all/），权威。
#   section / section_name / is_optional —— 取自灵神题单原文
#     https://leetcode.cn/discuss/post/3578981/
#     section 是 "§X.Y" 小节编号；「五、三指针」「六、分组循环」正文没有编号，
#     兜底成 "§5" / "§6"。is_optional 由该题所在小节标题或加粗的"思维扩展/
#     选做"标注决定。
#   is_premium —— 只认接口的 paid_only；本文件已把会员题整个丢弃（is_premium
#     恒为 false），因为当前使用者没有会员。
#   is_starred —— 题单原文不区分星标，这里恒为 false，留给使用者自己标。
#
# 不写 default_template：由 topic.yaml 的 section_templates 按最长前缀推导，
# 见 services/topics.py::resolve_section_template。
"""


def render_problems_yaml(problems: list[CatalogueProblem]) -> str:
    import yaml

    parts = [PROBLEMS_HEADER]
    for p in problems:
        entry = {
            "lc_id": p.lc_id,
            "title": p.title,
            "url": p.url,
            "difficulty": p.difficulty,
            "section": p.section,
            "section_name": p.section_name,
            "is_starred": False,
            "is_premium": False,
            "is_optional": p.is_optional,
        }
        block = yaml.safe_dump(
            [entry], allow_unicode=True, sort_keys=False, default_flow_style=False
        )
        parts.append(block)
    return "\n".join(parts)


# --------------------------------------------------------------------------
# 写 topic.yaml（只改 section_templates 那一段，其余原样保留）
# --------------------------------------------------------------------------


TOPIC_YAML_TEMPLATES_COMMENT = """\
# 题单按模板分节，按最长前缀匹配解析（services/topics.py::
# resolve_section_template），所以 §1.1/§1.2 都落到 "§1"：
#   §1    定长滑窗                       -> A
#   §2.1  越短越合法/求最长/最大          -> B
#   §2.2  越长越合法/求最短/最小          -> C
#   §2.3  求子数组个数                    -> D
#   §3.1  反转字符串（相向双指针的最简形态）-> E
#   §3.2  相向双指针                      -> E
#   §6    分组循环                        -> F
# 其余小节（§2.4、§3.3-§3.6、§4.x、§5）故意不写：使用者还没为这些写法准备
# 模板，default_template 解出 None 是设计好的结果，不是漏配。
# 取代逐题手标 default_template——见 problems.yaml 顶部注释和
# seed/bundle.py::_parse_problems。
"""


def update_topic_yaml(path: Path) -> None:
    import yaml

    text = path.read_text(encoding="utf-8")
    marker = "# 题单按模板分节"
    idx = text.find(marker)
    if idx == -1:
        raise RuntimeError(f"{path} 里没找到「{marker}」这段注释")
    head = text[:idx]

    lines = ["section_templates:"]
    for key, code in SECTION_TEMPLATES.items():
        lines.append(f'  "{key}": {code}')
    body = TOPIC_YAML_TEMPLATES_COMMENT + "\n".join(lines) + "\n"

    new_text = head + body
    path.write_text(new_text, encoding="utf-8")

    # 用真正的 YAML 解析器校验一遍改完之后的文件仍然合法。
    parsed = yaml.safe_load(new_text)
    assert parsed["section_templates"] == SECTION_TEMPLATES, parsed["section_templates"]


# --------------------------------------------------------------------------
# 写 plan_default.yaml
# --------------------------------------------------------------------------


def build_plan_days(non_optional: list[CatalogueProblem]) -> list[dict]:
    days: list[dict] = []
    seen_section_first_day: set[str] = set()

    for start in range(0, len(non_optional), PROBLEMS_PER_DAY):
        chunk = non_optional[start : start + PROBLEMS_PER_DAY]
        day_index = start // PROBLEMS_PER_DAY + 1

        # 出现顺序去重：一天内可能横跨 1-2 个小节（极少数情况下 2 个大节）。
        ordered_sections: list[str] = []
        section_to_major_theme: dict[str, tuple[str, str]] = {}
        for p in chunk:
            if p.section not in section_to_major_theme:
                ordered_sections.append(p.section)
                section_to_major_theme[p.section] = (p.section_name, p.section)

        # phase：涉及到的大节名，按首次出现顺序，多个用「；」拼接。
        ordered_majors: list[str] = []
        for p in chunk:
            major = p.section_name.split(" · ")[0]
            if major not in ordered_majors:
                ordered_majors.append(major)
        phase = "；".join(ordered_majors)

        theme_parts = []
        for section in ordered_sections:
            base_theme = SECTION_THEMES.get(section)
            if base_theme is None:
                raise RuntimeError(
                    f"§{section} 没有在 SECTION_THEMES 里配置主题文案，"
                    "但排期里出现了它的非选做题目"
                )
            if section not in seen_section_first_day:
                theme_parts.append(f"进入 {base_theme}")
                seen_section_first_day.add(section)
            else:
                theme_parts.append(base_theme)
        theme = "；".join(theme_parts)

        days.append(
            {
                "day_index": day_index,
                "phase": phase,
                "theme": theme,
                "problems": [p.lc_id for p in chunk],
            }
        )
    return days


def render_plan_yaml(days: list[dict]) -> str:
    import yaml

    doc = {
        "name": PLAN_NAME,
        "start_date": PLAN_START_DATE,
        "days": days,
    }
    # start_date 要以裸日期（date 对象）落地，不是字符串，否则 bundle.py 的
    # isinstance(start_date, date) 校验会失败。yaml.safe_dump 对
    # "YYYY-MM-DD" 格式的字符串默认按纯量输出、不加引号，safe_load 会把它
    # 解析回 datetime.date —— 和手写的 plan_default.yaml 效果一致。
    import datetime

    doc["start_date"] = datetime.date.fromisoformat(PLAN_START_DATE)
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, default_flow_style=False)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def main() -> int:
    # Windows 控制台默认代码页不是 UTF-8，重定向到文件时中文会被按 GBK 落盘、
    # 直接显示会乱码；显式切到 UTF-8，行为在各平台上保持一致。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print(f"抓取题单正文: {POST_URL}")
    markdown = fetch_post_markdown()
    parse_report = ParseReport()
    post_problems = parse_post(markdown, parse_report)
    print(f"  解析出 {len(post_problems)} 道题（已去重、已过滤非数字题号）")

    print(f"抓取官方接口: {API_URL}")
    api_by_id, skipped = fetch_api_problems()
    print(f"  接口共 {len(api_by_id)} 道纯数字题号的题（跳过 {skipped} 道非数字题号）")

    needed_ids = sorted({int(p.id_text) for p in post_problems if p.id_text.isdigit()})
    print(f"按 title_slug 补中文标题（GraphQL，共 {len(needed_ids)} 道，逐题请求）")
    enrich_with_chinese_titles(api_by_id, needed_ids)

    join_report = JoinReport()
    catalogue = join_sources(post_problems, api_by_id, join_report)

    non_optional = [p for p in catalogue if not p.is_optional]

    # --- 写 problems.yaml ---
    problems_path = TOPIC_DIR / "problems.yaml"
    problems_path.write_text(render_problems_yaml(catalogue), encoding="utf-8")

    # --- 更新 topic.yaml 的 section_templates ---
    update_topic_yaml(TOPIC_DIR / "topic.yaml")

    # --- 写 plan_default.yaml ---
    days = build_plan_days(non_optional)
    plan_path = TOPIC_DIR / "plan_default.yaml"
    plan_path.write_text(render_plan_yaml(days), encoding="utf-8")

    # --- 报告 ---
    print()
    print("=" * 70)
    print("小节统计（section / section_name / 总数 / 选做数）：")
    by_section: dict[str, dict] = {}
    for p in catalogue:
        d = by_section.setdefault(p.section, {"name": p.section_name.split(" · ")[-1] if " · " in p.section_name else p.section_name, "total": 0, "optional": 0})
        d["total"] += 1
        if p.is_optional:
            d["optional"] += 1
    for code in sorted(by_section, key=lambda c: [int(x) for x in c.lstrip("§").split(".")]):
        d = by_section[code]
        print(f"  {code:6s} {d['name']:24s} total={d['total']:3d}  optional={d['optional']:3d}")

    print()
    print(f"题库总数（非会员）: {len(catalogue)}")
    print(f"非选做题数: {len(non_optional)}")
    print(f"排期天数: {len(days)}")

    print()
    print(f"跳过的非数字题号（LCP/LCR/面试题等，{len(parse_report.non_numeric_ids)} 道）：")
    for line in parse_report.non_numeric_ids:
        print(f"  - {line}")

    print()
    print(f"题单正文内部重复（保留第一次出现，丢弃后续 {len(parse_report.duplicate_dropped)} 道）：")
    for lc_id, title in parse_report.duplicate_dropped:
        print(f"  - {lc_id}. {title}")

    print()
    print(f"标题不一致（题单 vs 接口，共 {len(join_report.title_mismatches)} 处，仅报告不阻断）：")
    for lc_id, post_title, api_title in join_report.title_mismatches:
        print(f"  - {lc_id}: 题单「{post_title}」 vs 接口「{api_title}」")

    print()
    print(f"会员题（丢弃，共 {len(join_report.premium_dropped)} 道）：{join_report.premium_dropped}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
