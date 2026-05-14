"""Configuration differ for comparing and rendering config changes.

This module provides the ConfigDiffer class, which parses two
configuration texts, compares them line-by-line using similarity
scoring, and renders an HTML representation of the differences.

It uses Jaccard similarity to match lines between pre and post
configurations, identifying additions, removals, and changes.

Module path: services/validators/config.py
"""

import textdistance


class ConfigDiffer:
    """Compare two configurations and render their differences."""

    DELIM = "\uF000"
    CHANGE_THRESHOLD_SCORE = 0.9

    def __init__(self, pre_config, post_config):
        """Initialize with pre and post configuration strings."""
        self.pre_config = pre_config
        self.post_config = post_config

        self.pre_parsed = {}
        self.post_parsed = {}

        self.results = {}
        self.tree = {}
        self.path_scores = {}

    def compare(self):
        """Compare pre and post configs and populate results."""
        self.pre_parsed = self._parse(self.pre_config)
        self.post_parsed = self._parse(self.post_config)
        used_post_lines = set()
        self.results = {}

        for line_num, pre_item in self.pre_parsed.items():
            pre_string = pre_item["string"]
            pre_path = pre_item["path"]
            pre_is_parent = pre_item["is_parent"]

            candidates = [
                item for item in self.post_parsed.values()
                if (
                        item["path"] == pre_path
                        and id(item) not in used_post_lines
                )
            ]

            best_match = None
            best_score = -1

            for candidate in candidates:
                post_string = candidate["string"]
                score = (
                    textdistance.jaccard.normalized_similarity(
                        pre_string.strip(), post_string.strip()
                    )
                )

                if pre_is_parent and score == 1.0:
                    best_match = candidate
                    best_score = score
                    break
                elif (
                        not pre_is_parent
                        and score >= self.CHANGE_THRESHOLD_SCORE
                        and score > best_score
                ):
                    best_match = candidate
                    best_score = score

            if best_match:
                is_matched = True
                used_post_lines.add(id(best_match))
                min_len = min(
                    len(pre_string), len(best_match["string"])
                )
                max_len = max(
                    len(pre_string), len(best_match["string"])
                )
                # Compute character positions that differ
                diff_positions = [
                    i for i in range(min_len)
                    if pre_string[i] != best_match["string"][i]
                ]
                diff_positions += list(range(min_len, max_len))
            else:
                is_matched = False
                best_match = {"string": ""}
                diff_positions = list(range(len(pre_string)))

            self.results[line_num] = {
                "string": pre_string,
                "best_match": best_match["string"],
                "is_parent": pre_is_parent,
                "similarity_score": best_score,
                "is_matched": is_matched,
                "diff_positions": diff_positions,
                "path": pre_path,
            }

        # Collect unmatched post-config lines as additions
        next_line = max(self.results.keys(), default=0) + 1
        for post_item in self.post_parsed.values():
            if id(post_item) in used_post_lines:
                continue

            self.results[next_line] = {
                "string": post_item["string"],
                "best_match": "",
                "is_parent": post_item["is_parent"],
                "similarity_score": -2,
                "is_matched": False,
                "diff_positions": list(
                    range(len(post_item["string"]))
                ),
                "path": post_item["path"],
                "is_added": True,
            }
            next_line += 1

    def render(self):
        """Render comparison results as an HTML string."""
        self._build_tree()

        html = []

        global_items = self.tree.pop("root_items", [])
        if global_items:
            html.append(
                self._render_section(
                    "global", {"root_items": global_items}, depth=0
                )
            )

        for section, subtree in self.tree.items():
            html.append(
                self._render_section(section, subtree, depth=0)
            )

        return "\n".join(html)

    def _parse(self, config):
        """Parse a config string into a structured dictionary."""
        lines = config.splitlines()
        result = {}
        path_stack = []

        def indent(line):
            """Return the indentation level of a line."""
            return len(line) - len(line.lstrip(" "))

        for i, line in enumerate(lines):
            stripped_line = line.strip()

            if not stripped_line:
                continue

            indent_level = indent(line)

            while (
                    path_stack
                    and path_stack[-1][0] >= indent_level
            ):
                path_stack.pop()

            current_path = self.DELIM.join(
                part[1] for part in path_stack
            )

            # Determine if this line is a parent by checking
            # if the next non-empty line is more indented
            is_parent = False
            for j in range(i + 1, len(lines)):
                if lines[j].strip():
                    if indent(lines[j]) > indent_level:
                        is_parent = True
                    break

            result[len(result) + 1] = {
                "string": stripped_line,
                "path": current_path,
                "is_parent": is_parent,
            }

            path_stack.append((indent_level, stripped_line))

        return result

    def _build_tree(self):
        """Build a nested tree structure from comparison results."""
        self.tree = {}
        self.path_scores = {}

        for item in self.results.values():
            path = (
                [item["path"], item["string"]]
                if item["path"]
                else [item["string"]]
            )

            self.path_scores[self.DELIM.join(path)] = item.get(
                "similarity_score", 0
            )

            node = self.tree
            if item["path"]:
                for part in item["path"].split(self.DELIM):
                    node = node.setdefault(part, {})

            if not (item["is_parent"] and not item["is_matched"]):
                node.setdefault("root_items", []).append(item)

    def _render_section(self, title, subtree, depth=0):
        """Render a tree section as an HTML card element."""
        section = []

        for key, value in subtree.items():
            if key == "root_items":
                section.extend(
                    self._render_item(item) for item in value
                )
            else:
                section.append(
                    self._render_section(key, value, depth + 1)
                )

        if not section:
            return ""

        state = self._get_section_state(subtree)
        card_cls = (
            f"card is-{state}" if state else "card"
        )

        return (
            f'<div class="{card_cls}" data-depth="{depth}"'
            f' style="--depth: {depth};">'
            f'<div class="card-header">'
            f'<span class="material-icons toggle-icon">'
            f"expand_more</span>"
            f'<span class="card-title">{title}</span>'
            f"</div>"
            f'<div class="card-body">'
            f"{''.join(section)}"
            f"</div>"
            f"</div>"
        )

    def _render_item(self, item):
        """Render a single diff item as HTML."""
        if item.get("is_added"):
            return self._render_simple_item(
                item, "is-added", "add"
            )
        if not item["is_matched"]:
            return self._render_simple_item(
                item, "is-removed", "remove"
            )
        if item["similarity_score"] < 1.0:
            return self._render_changed_item(item)
        if item["is_parent"]:
            return ""

        return self._render_simple_item(
            item, "is-unchanged", "equal"
        )

    def _render_simple_item(self, item, cls, icon):
        """Render an item with a single status indicator."""
        return (
            f'<div class="item {cls}" data-type="{cls}">'
            f'<span class="material-icons">{icon}</span>'
            f'{item["string"]}'
            f"</div>"
        )

    def _render_changed_item(self, item):
        """Render an item that has changed between configs."""
        left = self._highlight_diff(
            item["string"], item["diff_positions"]
        )
        right = self._highlight_diff(
            item["best_match"], item["diff_positions"]
        )

        return (
            f'<div class="item is-changed" '
            f'data-type="is-changed">'
            f'<span class="material-icons">'
            f"compare_arrows</span>"
            f"{left}"
            f'<span class="material-icons">'
            f"arrow_forward</span>"
            f"{right}"
            f"</div>"
        )

    def _get_section_state(self, subtree):
        """Determine the visual state of a tree section."""
        items = subtree.get("root_items")
        if not items:
            return None

        score = self.path_scores.get(items[0].get("path"))
        return {-1: "removed", -2: "added"}.get(score)

    def _highlight_diff(self, text, diff_positions):
        """Wrap differing characters in highlight spans."""
        if not diff_positions:
            return text

        diff_set = set(diff_positions)
        out = [
            f'<span class="diff-char">{ch}</span>'
            if i in diff_set else ch
            for i, ch in enumerate(text)
        ]
        return "".join(out)
