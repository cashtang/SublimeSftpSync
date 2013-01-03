import sublime
import sublime_plugin
from sftpsync_module import PSCPCommand
import functools


class SftpSyncCommand(sublime_plugin.WindowCommand):
    def run(self, upload=True, allopenfile=False, encoding='utf-8'):
        self.encoding = encoding
        #sublime.message_dialog(u'enter sftpsync plugin')
        if allopenfile:
            if not sublime.ok_cancel_dialog(u'Sync all open files?'):
                return
            self.output_view = self.window.get_output_panel('sftpsync')
            self.window.run_command("show_panel", {"panel": "output.sftpsync"})
            views = self.window.views()
            for view in views:
                self._sync_file(upload, view)
        else:
            self.output_view = self.window.get_output_panel('sftpsync')
            self.window.run_command("show_panel", {"panel": "output.sftpsync"})
            view = self.window.active_view()
            self._sync_file(upload, view)

    def _sync_file(self, upload, view):
        if view.is_dirty():
            if sublime.ok_cancel_dialog(u'Save file [%s] first?' % view.file_name()):
                sublime.run_command("save")
                if view.is_dirty():
                    sublime.message_dialog(u'Save file failed!!')
                    return

        pscp = PSCPCommand(self)
        # sublime.message_dialog(u"begin 1")
        pscp.transferFile(view.file_name(), upload)
        #self._append_data(u"SftpSync file %s error" % view.name())

    def append_data(self, msg):
        try:
            msg = msg.decode(self.encoding)
        except:
            msg = 'Output is not encoding ' + self.encoding
        self.output_view.set_read_only(False)
        edit = self.output_view.begin_edit()
        self.output_view.insert(edit, self.output_view.size(), msg + '\n')
        self.output_view.end_edit(edit)
        self.output_view.set_read_only(True)

    def finish(self, proc):
        self.window.run_command("show_panel", {"panel": "output.sftpsync"})
        self.show_status('operation finished')

    def show_status(self, msg):
        self.output_view.set_read_only(False)
        edit = self.output_view.begin_edit()
        self.output_view.insert(edit, self.output_view.size(), msg + '\n')
        self.output_view.end_edit(edit)
        self.output_view.set_read_only(True)

    def on_data(self, proc, data):
        sublime.set_timeout(functools.partial(self.append_data, data), 0)

    def on_finished(self, proc):
        sublime.set_timeout(functools.partial(self.finish, proc), 0)
