#!/usr/bin/env python3
"""
自动检查生成的SKILL.md是否通过Phase 4质量标准。
对照通过标准表格逐项检查，输出通过/不通过和具体原因。

用法:
    python3 quality_check.py <SKILL.md路径>

示例:
    python3 quality_check.py .claude/skills/elon-musk-perspective/SKILL.md
"""

import sys
import re
from pathlib import Path


def get_section(content: str, title_pattern: str, level: int = 2) -> str | None:
    """按标题行切出章节：从匹配的标题行起，到下一个同级或更高级标题前止。

    只在标题行内匹配 title_pattern，避免正则跨行误匹配到别处。
    """
    lines = content.split('\n')
    start = None
    for i, line in enumerate(lines):
        m = re.match(r'^(#{1,6})\s+(.*)$', line)
        if not m:
            continue
        depth = len(m.group(1))
        if start is None:
            if depth <= level and re.search(title_pattern, m.group(2), re.IGNORECASE):
                start, start_depth = i, depth
        elif depth <= start_depth:
            return '\n'.join(lines[start + 1:i])
    return '\n'.join(lines[start + 1:]) if start is not None else None


def count_list_items(text: str) -> int:
    """数列表项：支持 - * 短横线/星号列表，以及 1. 2. 编号列表。"""
    return len(re.findall(r'^\s*(?:[-*]|\d+[.)])\s+', text, re.MULTILINE))


def check_mental_models(content: str) -> tuple[bool, str]:
    """检查心智模型数量（3-7个）"""
    # 匹配 ### 模型N: 或 ### N. 等模式
    models = re.findall(r'^###\s+(?:模型|Model|心智模型)\s*\d', content, re.MULTILINE)
    if not models:
        # fallback: 数「### 」开头的行在心智模型section中
        in_section = False
        count = 0
        for line in content.split('\n'):
            if re.match(r'^##\s+.*心智模型|Mental Model', line, re.IGNORECASE):
                in_section = True
                continue
            if in_section and re.match(r'^##\s+', line) and '心智模型' not in line:
                break
            if in_section and re.match(r'^###\s+', line):
                count += 1
        if count > 0:
            passed = 3 <= count <= 7
            return passed, f"{count}个心智模型 {'✅' if passed else '❌ (应为3-7个)'}"

    count = len(models)
    if count == 0:
        return False, "未检测到心智模型section"
    passed = 3 <= count <= 7
    return passed, f"{count}个心智模型 {'✅' if passed else '❌ (应为3-7个)'}"


def check_limitations(content: str) -> tuple[bool, str]:
    """检查每个心智模型是否都有局限性"""
    section = get_section(content, r'心智模型|Mental Model')
    if section is None:
        has = bool(re.search(r'局限|失效|不适用|盲区|limitation|blind spot', content, re.IGNORECASE))
        return has, "有局限性标注 ✅" if has else "❌ 未找到局限性描述"

    blocks = re.split(r'^###\s+', section, flags=re.MULTILINE)[1:]
    if not blocks:
        has = bool(re.search(r'局限|失效|不适用|盲区|limitation|blind spot', section, re.IGNORECASE))
        return has, "有局限性标注 ✅" if has else "❌ 未找到局限性描述"

    missing = [b.split('\n', 1)[0].strip() for b in blocks
               if not re.search(r'局限|失效|不适用|盲区|limitation|blind spot', b, re.IGNORECASE)]
    if missing:
        return False, f"❌ {len(missing)}个模型缺局限性: {'; '.join(missing)[:60]}"
    return True, f"{len(blocks)}个模型均有局限性 ✅"


def check_expression_dna(content: str) -> tuple[bool, str]:
    """检查表达DNA辨识度"""
    dna_section = bool(re.search(r'表达DNA|Expression DNA|表达风格', content, re.IGNORECASE))
    if not dna_section:
        return False, "❌ 未找到表达DNA section"

    # 检查是否有具体的风格描述（句式、词汇等）
    style_markers = len(re.findall(r'句式|词汇|语气|幽默|节奏|确定性|引用|口头禅', content))
    passed = style_markers >= 3
    return passed, f"表达DNA特征: {style_markers}项 {'✅' if passed else '❌ (应≥3项)'}"


def check_honest_boundary(content: str) -> tuple[bool, str]:
    """检查诚实边界（至少3条）"""
    boundary = get_section(content, r'诚实边界|Honest Boundar')
    if boundary is None:
        return False, "❌ 未找到诚实边界section"

    count = count_list_items(boundary)
    passed = count >= 3
    return passed, f"诚实边界: {count}条 {'✅' if passed else '❌ (应≥3条)'}"


def check_tensions(content: str) -> tuple[bool, str]:
    """检查内在张力（至少2对）"""
    tension_markers = len(re.findall(r'张力|矛盾|tension|paradox|一方面.*另一方面|既.*又', content, re.IGNORECASE))
    passed = tension_markers >= 2
    return passed, f"内在张力: {tension_markers}处 {'✅' if passed else '❌ (应≥2处)'}"


def check_primary_sources(content: str) -> tuple[bool, str]:
    """检查一手来源占比（按列表项计数，而非数关键词）"""
    source_text = get_section(content, r'来源|信息源|Source|Reference')
    if source_text is None:
        return True, "未找到来源section（跳过检查）"

    primary = secondary = 0
    mode = None
    for line in source_text.split('\n'):
        label = re.match(r'^(?:#{3,6}\s+|\*\*)(.*)', line)
        if label and re.search(r'一手|二手|外部批评|primary|secondary', label.group(1), re.IGNORECASE):
            mode = 'p' if re.search(r'一手|primary', label.group(1), re.IGNORECASE) else 's'
            # 行内写法：**一手来源**：A、B、C
            inline = re.split(r'[：:]', line, maxsplit=1)
            if len(inline) == 2 and inline[1].strip():
                n = len([x for x in re.split(r'[、;；]', inline[1]) if x.strip()])
                if mode == 'p':
                    primary += n
                else:
                    secondary += n
            continue
        if mode and re.match(r'^\s*(?:[-*]|\d+[.)])\s+', line):
            if mode == 'p':
                primary += 1
            else:
                secondary += 1
        elif re.match(r'^#{1,6}\s', line):
            mode = None

    total = primary + secondary
    if total == 0:
        return True, "未标记来源类型（跳过检查）"

    ratio = primary / total
    passed = ratio > 0.5
    return passed, f"一手来源占比: {primary}/{total} ({ratio:.0%}) {'✅' if passed else '❌ (应>50%)'}"


def main():
    if len(sys.argv) < 2:
        print("用法: python3 quality_check.py <SKILL.md路径>")
        sys.exit(1)

    skill_path = Path(sys.argv[1])
    if not skill_path.exists():
        print(f"❌ 文件不存在: {skill_path}")
        sys.exit(1)

    content = skill_path.read_text(encoding='utf-8')

    checks = [
        ("心智模型数量", check_mental_models),
        ("模型局限性", check_limitations),
        ("表达DNA辨识度", check_expression_dna),
        ("诚实边界", check_honest_boundary),
        ("内在张力", check_tensions),
        ("一手来源占比", check_primary_sources),
    ]

    print(f"质量检查: {skill_path.name}")
    print("=" * 50)

    passed_count = 0
    total = len(checks)

    for name, check_fn in checks:
        passed, detail = check_fn(content)
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name:<12} {status}  {detail}")
        if passed:
            passed_count += 1

    print("=" * 50)
    print(f"结果: {passed_count}/{total} 通过")

    if passed_count == total:
        print("🎉 全部通过，可以交付")
    elif passed_count >= total - 1:
        print("⚠️ 基本通过，建议修复不通过项后交付")
    else:
        print("❌ 多项不通过，建议回到Phase 2迭代")

    sys.exit(0 if passed_count == total else 1)


if __name__ == '__main__':
    main()
