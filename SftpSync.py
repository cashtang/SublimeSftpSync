import sublime
import sublime_plugin
import functools
import os
import socket
import paramiko

class SftpTools(object):
    def __init__(self):
        super(SftpTools, self).__init__()

    def execute(self, transform_files, host, user, password, port=22):
        hostkeytype = None
        hostkey = None
        host_keys = self._load_host_keys()
        if host_keys.has_key(host):
            hostkeytype = host_keys[host].keys()[0]
            hostkey = host_keys[host][hostkeytype]

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((host, port))
            t = paramiko.Transport(sock)
            t.connect(username=user, password=password, hostkey=hostkey)
            sftp = paramiko.SFTPClient.from_transport(t)
            self._transform(sftp, transform_files)
            t.close()
            return True, 'OK'
        except Exception as e:
            msg = u"Load Error,<{0}>".format(e)
            return False, msg

    def upload(self, source_file):
        pass

    def _transform(self, sftp, file_list):
        for src, dst in file_list:
            dst_dir = os.path.dirname(dst)
            try:
                sftp.mkdir(dst_dir)
            except IOError:
                pass
            sftp.put(src, dst)

    def _load_host_keys(self):
        try:
            host_keys = paramiko.util.load_host_keys(os.path.expanduser('~/.ssh/known_hosts'))
        except IOError:
            try:
                host_keys = paramiko.util.load_host_keys(os.path.expanduser('~/ssh/known_hosts'))
            except IOError:
                return {}
        return host_keys

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

        sftp = SftpTools()
        settings = view.settings()
        hostname = settings.get('sftp_hostname')
        port = settings.get('sftp_port', 22)
        user = settings.get('sftp_user')
        password = settings.get('sftp_password')
        remote_basedir = settings.get("sftp_remote_basedir")

        relative_path = self._guess_relative_path(view)
        remote_path = os.path.join(remote_basedir, relative_path)
        r, msg = sftp.execute((view.file_name(), remote_path), hostname, user, password, port)
        if r:
            self.show_status(u"Upload file success!")
        else:
            self.show_status(msg)

    def _guess_relative_path(self, view):
        file_name = view.file_name()
        for f in self.window.folders():
            if file_name.startswith(f):
                return file_name[len(f) + 1:]
        return file_name

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
