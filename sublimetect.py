import sublime, sublime_plugin
import re
import urllib.request


INDENT_RE = re.compile('^\s*')

def line_indent(view, row):
    pt = view.text_point(row,0)
    line = view.full_line(pt)
    content = view.substr(line)
    if len(content) <= 1:
        return 10000 # blank lines have arbitrarily high indent
    start,end = INDENT_RE.match(content).span(0)
    return end-start

def find_function_bodies(view, decls):
    last_row, last_col = view.rowcol(view.size())
    fold_regions = []
    for decl in decls:
        line_region = view.full_line(decl)
        start_row, _ = view.rowcol(decl.a)
        end_row, _ = view.rowcol(decl.b)
        fn_indent = line_indent(view, start_row)

        # find lines until closed indent
        cur_row = end_row+1
        while True:
            if cur_row == last_row:
                break
            indent = line_indent(view, cur_row)
            if indent <= fn_indent:
                break
            cur_row += 1

        # compute region
        if (cur_row - end_row) > 1:
            final_line = view.full_line(view.text_point(cur_row, 0))
            if final_line.size() > 4:
                # for languages like python, or when the end is otherwise long
                # collapse just before the closing bit
                end_pt = view.text_point(cur_row-1,0)
            else:
                final_line_indent = line_indent(view, cur_row)
                end_pt = view.text_point(cur_row, final_line_indent)
            fold_regions.append(sublime.Region(line_region.b-1, end_pt))

    return fold_regions


def find_all_functions(view):
    if view.score_selector(0,'source.rust') > 0:
        fn_bodies = view.find_by_selector('meta.function meta.block')
        folds = [sublime.Region(r.a+1,r.b-1) for r in fn_bodies]
    else:
        fn_decls = view.find_by_selector('meta.function, entity.name.function')
        folds = find_function_bodies(view, fn_decls)
    return folds

REMOVE_WHITESPACE = re.compile(r"\n\s*")
MAX_LINE_LEN = 100
def find_short_ifs(view):
    folds = []
    cur_pt = 0
    for i in range(1000): # limited in case bugs, could be while True
        if_stmt = view.find(r" +if[ \(](.*)[ \)]\{\n[^\{\}\n]*\n\s*\}", cur_pt)
        if if_stmt is None or if_stmt.empty():
            break # no more found


        # check that if we folded it the line wouldn't be too long
        stmt = view.substr(if_stmt)
        stmt = REMOVE_WHITESPACE.sub(" ", stmt)
        if len(stmt) > MAX_LINE_LEN:
            continue

        print(stmt)

        # find the parts to fold, this is kinda overkill
        sub_pt = if_stmt.begin()
        for i in range(10): # limited in case bugs, could be while True
            line_break = view.find(r"\n\s*", sub_pt)
            if line_break is None or line_break.empty() or line_break.begin() >= if_stmt.end():
                break # no more found
            folds.append(line_break)
            sub_pt = line_break.end()

        # move past this one
        cur_pt = if_stmt.end()

    return folds


class SelectLineCommand(sublime_plugin.TextCommand):
    def is_selection_lines(self):
        for selection in self.view.sel():
            if not selection.empty():
                return True
        return False

    def reverse_selections(self):
        sels = self.view.sel()

        newSels = []
        for sel in sels:
            newSels.append(sublime.Region(sel.b, sel.a))

        sels.clear()
        for sel in newSels:
            sels.add(sel)

    def run(self, edit, **args):
        if not ('forward' in args):
            return

        if not self.is_selection_lines():
            self.view.run_command('expand_selection',{'to': 'line'})
            if args['forward']:
                return
            else:
                self.reverse_selections()

        cmd = 'move'
        cmd_args = {'by': 'lines', 'forward': args['forward'], 'extend': True}

        self.view.run_command(cmd, cmd_args)

class FoldScopesCommand(sublime_plugin.TextCommand):
    def run(self, edit, **args):
        selector = args.get('selector') or 'meta.function meta.block'
        folds = self.view.find_by_selector(selector)
        # print("folding " + len(folds))
        did_fold = self.view.fold(folds)
        if not did_fold: # already folded, toggle off
            self.view.unfold(folds)

class FoldFunctionsCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        folds = find_all_functions(self.view)
        # print("folding " + len(folds))
        did_fold = self.view.fold(folds)
        if not did_fold: # already folded, toggle off
            self.view.unfold(folds)

class FoldShortStuffCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        print("lol")
        folds = find_short_ifs(self.view)
        # print("folding " + len(folds))
        did_fold = self.view.fold(folds)
        if not did_fold: # already folded, toggle off
            self.view.unfold(folds)

class AutoMaxPaneCommand(sublime_plugin.WindowCommand):
    """Toggles pane maximization based on view size."""
    def run(self):
        view = self.window.active_view()
        if view is None:
            return

        width = self.get_window_width()
        self.set_maximized(width < 980.0)

    def get_window_width(self):
        """The only way I can figure out to get the width of the window."""
        max_right_edge = 0.0
        for i in range(self.window.num_groups()):
            v = self.window.active_view_in_group(i)
            ex, ey = v.viewport_extent()
            if ex == 0.0:
                continue
            lx, ly = v.window_to_layout((0,0))
            px, py = v.viewport_position()
            ox = -(lx - px)
            right_edge = ox + ex

            # re2, _ = v.layout_to_window((ex+px-0.1,py+0.1))
            # print((right_edge, re2, lx, px, ox, ex))
            if right_edge > max_right_edge:
                max_right_edge = right_edge

        return max_right_edge

    def set_maximized(self, maximize):
        # print("automax: {}".format(maximize))
        from MaxPane.max_pane import PaneManager, ShareManager
        w = self.window
        if maximize:
            if w.num_groups() > 1 and not PaneManager.isWindowMaximized(w):
                ShareManager.add(w.id())
                w.run_command("maximize_pane")
        elif PaneManager.isWindowMaximized(w):
            w.run_command("unmaximize_pane")
            ShareManager.remove(w.id())

class SyncCodeCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        file_name = self.view.file_name()
        if not file_name:
            return
        pt = self.view.sel()[0].a
        row, col = self.view.rowcol(pt)

        req = urllib.request.Request('http://localhost:7143/')
        req.add_header('x-file', file_name)
        req.add_header('x-row', str(row))
        req.add_header('x-col', str(col))
        with urllib.request.urlopen(req) as f:
            pass

class GoDownNoCompleteCommand(sublime_plugin.TextCommand):
    def run(self, edit, **args):
        if self.view.is_auto_complete_visible():
            self.view.run_command('hide_auto_complete')
            sublime.set_timeout(lambda: self.view.run_command('move', {"by":"lines", "forward": True}), 0)
        else:
            self.view.run_command('move', {"by":"lines", "forward": True})
