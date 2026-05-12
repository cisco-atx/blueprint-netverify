import textdistance

class ConfigDiffer:
    DELIM = "\uF000"
    CHANGE_THRESHOLD_SCORE = 0.9

    def __init__(self, pre_config, post_config):
        self.pre_config = pre_config
        self.post_config = post_config

        self.pre_parsed = {}
        self.post_parsed = {}

        self.results = {}
        self.tree = {}
        self.path_scores = {}

    def compare(self):
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
                if item["path"] == pre_path and id(item) not in used_post_lines
            ]

            best_match = None
            best_score = -1

            for candidate in candidates:
                post_string = candidate["string"]
                score = textdistance.jaccard.normalized_similarity(pre_string.strip(), post_string.strip())

                if pre_is_parent and score == 1.0:
                    best_match = candidate
                    best_score = score
                    break
                elif not pre_is_parent and score >= self.CHANGE_THRESHOLD_SCORE and score > best_score:
                    best_match = candidate
                    best_score = score

            if best_match:
                is_matched = True
                used_post_lines.add(id(best_match))
                diff_positions = [i for i in range(min(len(pre_string), len(best_match["string"]))) if
                                  pre_string[i] != best_match["string"][i]]
                diff_positions += list(range(min(len(pre_string), len(best_match["string"])),
                                             max(len(pre_string), len(best_match["string"]))))
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
                "diff_positions": list(range(len(post_item["string"]))),
                "path": post_item["path"],
                "is_added": True,
            }
            next_line += 1

    def render(self):
        self._build_tree()

        html = []

        global_items = self.tree.pop("root_items", [])
        if global_items:
            html.append(self._render_section("global", {"root_items": global_items}, depth=0))

        for section, subtree in self.tree.items():
            html.append(self._render_section(section, subtree, depth=0))

        return "\n".join(html)

    def _parse(self, config):
        lines = config.splitlines()
        result = {}
        path_stack = []

        def indent(line):
            return len(line) - len(line.lstrip(" "))

        for i, line in enumerate(lines):
            stripped_line = line.strip()

            if not stripped_line:
                continue

            indent_level = indent(line)

            while (path_stack and path_stack[-1][0] >= indent_level):
                path_stack.pop()

            current_path = self.DELIM.join(part[1] for part in path_stack)

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
        self.tree = {}
        self.path_scores = {}

        for item in self.results.values():
            path = ([item["path"], item["string"]] if item["path"] else [item["string"]])

            self.path_scores[self.DELIM.join(path)] = item.get("similarity_score", 0)

            node = self.tree
            if item["path"]:
                for part in item["path"].split(self.DELIM):
                    node = node.setdefault(part, {})

            if not (item["is_parent"] and not item["is_matched"]):
                node.setdefault("root_items",[]).append(item)

    def _render_section(self, title, subtree, depth=0):
        section = []

        for key, value in subtree.items():
            if key == "root_items":
                section.extend(self._render_item(item) for item in value)
            else:
                section.append(self._render_section(key, value, depth + 1))

        if not section:
            return ""

        state = self._get_section_state(subtree)
        card_cls = f"card is-{state}" if state else "card"

        return f'''
            <div class="{card_cls}" data-depth="{depth}" style="--depth: {depth};">
                <div class="card-header">
                    <span class="material-icons toggle-icon">expand_more
                    </span>
                    <span class="card-title">{title}</span>
                </div>
                <div class="card-body">
                    {''.join(section)}
                </div>
            </div>
        '''

    def _render_item(self, item):
        if item.get("is_added"): return self._render_simple_item(item, "is-added", "add")
        if not item["is_matched"]: return self._render_simple_item(item, "is-removed", "remove")
        if item["similarity_score"] < 1.0: return self._render_changed_item(item)
        if item["is_parent"]: return ""

        return self._render_simple_item(item, "is-unchanged", "equal")

    def _render_simple_item(self, item, cls, icon):
        return (
            f'<div class="item {cls}" data-type="{cls}">'
            f'<span class="material-icons">{icon}</span>'
            f'{item["string"]}'
            f'</div>'
        )

    def _render_changed_item(self, item):
        left = self._highlight_diff(item["string"], item["diff_positions"])
        right = self._highlight_diff(item["best_match"], item["diff_positions"])

        return (
            f'<div class="item is-changed" data-type="is-changed">'
            f'<span class="material-icons">compare_arrows</span>'
            f'{left}<span class="material-icons">arrow_forward</span>{right}'
            f'</div>'
        )

    def _get_section_state(self, subtree):
        items = subtree.get("root_items")
        if not items:
            return None

        score = self.path_scores.get(items[0].get("path"))
        return {-1: "removed", -2: "added"}.get(score)

    def _highlight_diff(self, text, diff_positions):
        if not diff_positions:
            return text

        out = []
        for i, ch in enumerate(text):
            out.append(f'<span class="diff-char">{ch}</span>') if i in diff_positions else out.append(ch)
        return "".join(out)