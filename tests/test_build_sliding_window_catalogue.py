"""scripts/build_sliding_window_catalogue.py 的题单正文解析器测试。

只测 parse_post 这一个纯函数（不发任何网络请求）：markdown 是喂进去的字符串，
不是抓来的。scripts/ 不是一个包，所以用 importlib 按文件路径直接加载模块。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "build_sliding_window_catalogue.py"

_spec = importlib.util.spec_from_file_location("build_sliding_window_catalogue", MODULE_PATH)
_module = importlib.util.module_from_spec(_spec)
# dataclasses' postponed-annotation handling looks the module up in
# sys.modules by name while exec_module runs -- register it first, or the
# @dataclass decorators on ApiProblem/PostProblem/etc. blow up.
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)

parse_post = _module.parse_post
ParseReport = _module.ParseReport


def test_optional_scoping_is_the_or_of_three_independently_reset_markers():
    """回归用例，直接复现曾经出现过的 bug：

    - 一道题落在非选做的 "### " 小节下，但它自己所在的 "#### " 四级标题写了
      "选做" -> 必须是选做题（这是 §2.1.2 那种情况：父级 §2.1 本身不选做，
      §2.1.2 才是"进阶（选做）"）。
    - 一条加粗细化（"**思维扩展**"）打开的选做状态，必须在下一个 "#### "
      标题出现时被关闭，不能一路蔓延到后面不相关的四级小节（这是 §2.3 曾经
      出现过的 bug：§2.3.1 里的"思维扩展（选做）"吞掉了 §2.3.2/§2.3.3 的
      正常题目）。
    - 新的 "#### " 标题本身不写关键词时，必须显式把加粗标记也清空，而不是
      继承上一个 "#### " 块残留的状态。
    """
    markdown = """
## 一、测试大节

### §1.1 普通小节

- [1. 甲](https://leetcode.cn/problems/a/)

#### §1.1.2 进阶（选做）

- [2. 乙](https://leetcode.cn/problems/b/)

#### §1.1.3 普通

- [3. 丙](https://leetcode.cn/problems/c/)

**思维扩展**：

- [4. 丁](https://leetcode.cn/problems/d/)

#### §1.1.4 下一个四级标题

- [5. 戊](https://leetcode.cn/problems/e/)
"""
    report = ParseReport()
    problems = parse_post(markdown, report)
    by_id = {int(p.id_text): p for p in problems}

    assert len(problems) == 5

    # 1：在 "### §1.1"（不选做）下，还没进入任何 "#### "，非选做。
    assert by_id[1].is_optional is False
    assert by_id[1].section == "§1.1"  # #### 不产生新的 section code

    # 2：所在的 "#### §1.1.2 进阶（选做）" 自己写了"选做" -> 选做，即使父级
    # "### §1.1" 本身不选做。这是 §2.1.2 那个 bug 的最小复现。
    assert by_id[2].is_optional is True
    assert by_id[2].section == "§1.1"

    # 3：进入了新的 "#### §1.1.3 普通"（不含关键词）-> 必须显式清空，不能
    # 继承上一个 "#### §1.1.2" 的选做状态。
    assert by_id[3].is_optional is False

    # 4：在 "#### §1.1.3" 内部出现的 "**思维扩展**" 加粗细化把状态打开。
    assert by_id[4].is_optional is True

    # 5：新的 "#### §1.1.4"（不含关键词）出现后，加粗标记必须被清空，不能
    # 像 §2.3 那次回归一样一路蔓延下去。
    assert by_id[5].is_optional is False


def test_new_section_heading_clears_subsection_and_bold_markers():
    """"### " 换到新小节时，必须把 "#### " 和加粗细化两层标记都清空——否则
    上一个小节末尾的选做状态会渗进下一个完全不相关的小节。
    """
    markdown = """
## 一、测试大节

### §1.1 选做小节（选做）

#### §1.1.1 子块

- [1. 甲](https://leetcode.cn/problems/a/)

### §1.2 正常小节

- [2. 乙](https://leetcode.cn/problems/b/)
"""
    report = ParseReport()
    problems = parse_post(markdown, report)
    by_id = {int(p.id_text): p for p in problems}

    assert by_id[1].is_optional is True  # 继承自 "### §1.1"（选做）
    assert by_id[2].is_optional is False  # 新的 "### §1.2" 已经清空了状态
