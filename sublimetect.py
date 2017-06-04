import sublime, sublime_plugin

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
