#!/usr/bin/env
# -*- coding: utf-8 -*-
import os
import sys
import ConfigParser
import subprocess
import thread
import time
import sublime
CFGFILENAME = 'sftpcfg.ini'


def _get_plugin_path():
    plugin = os.path.realpath(sublime.packages_path())
    plugin = os.path.join(plugin, "SublimeSftpSync")
    return plugin

#PLUGINPATH = _get_plugin_path()


class AsyncProcess(object):
    def __init__(self, arg_list, env, listener,
            # "path" is an option in build systems
            path="",
            # "shell" is an options in build systems
            shell=False):

        self.listener = listener
        self.killed = False

        self.start_time = time.time()

        # Hide the console window on Windows
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        # Set temporary PATH to locate executable in arg_list
        if path:
            old_path = os.environ["PATH"]
            # The user decides in the build system whether he wants to append $PATH
            # or tuck it at the front: "$PATH;C:\\new\\path", "C:\\new\\path;$PATH"
            os.environ["PATH"] = os.path.expandvars(path).encode(sys.getfilesystemencoding())

        proc_env = os.environ.copy()
        if env:
            proc_env.update(env)
        for k, v in proc_env.iteritems():
            proc_env[k] = os.path.expandvars(v).encode(sys.getfilesystemencoding())
        self.proc = subprocess.Popen(arg_list, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, startupinfo=startupinfo, env=proc_env, shell=shell)

        if path:
            os.environ["PATH"] = old_path

        if self.proc.stdout:
            thread.start_new_thread(self.read_stdout, ())

        if self.proc.stderr:
            thread.start_new_thread(self.read_stderr, ())

    def kill(self):
        if not self.killed:
            self.killed = True
            self.proc.terminate()
            self.listener = None

    def poll(self):
        return self.proc.poll() == None

    def exit_code(self):
        return self.proc.poll()

    def read_stdout(self):
        while True:
            data = os.read(self.proc.stdout.fileno(), 2 ** 15)

            if data != "":
                if self.listener:
                    self.listener.on_data(self, data)
            else:
                self.proc.stdout.close()
                if self.listener:
                    self.listener.on_finished(self)
                break

    def read_stderr(self):
        while True:
            data = os.read(self.proc.stderr.fileno(), 2 ** 15)

            if data != "":
                if self.listener:
                    self.listener.on_data(self, data)
            else:
                self.proc.stderr.close()
                break


class PSCPCfg:
    def __init__(self):
        self.svrip = ''
        self.svrport = 22
        self.srcfile = ''
        self.svruser = 'root'
        self.svruserpwd = ''
        self.svrkeyfile = ''
        self.svrbasepath = '/'
        self.timeout = 30

    def load_config(self, cfgfile):
        parser = ConfigParser.RawConfigParser()
        parser.read(cfgfile)
        cfgs = dict(parser.items('BASE'))
        self.svrip = cfgs.get('svrip')
        #self.svrport = parser.getint('BASE','svrport')
        if self.svrport == 0:
            self.svrport = 22
        self.svruser = cfgs.get('svruser')
        self.svruserpwd = cfgs.get('svruserpwd')
        self.svrkeyfile = cfgs.get('svrkeyfile')
        self.svrbasepath = cfgs.get('svrbasepath')
        self.timeout = int(cfgs.get('timeout', 10))
        if len(self.svrbasepath) == 0:
            self.svrbasepath = '/'


class PSCPCommand:
    def __init__(self, listener):
        self.pscp_cfg_ = PSCPCfg()
        self.relative_path_ = ''
        self.listener = listener
        self.proc = None

    def _findCfgForPath(self, dirpath):
        """ 检查路径 sftp.ini 配置文件
        """
        checkpath = dirpath
        self.relative_path_ = ''
        while 1:
            cfgdir = os.path.join(checkpath, CFGFILENAME)
            if os.path.isfile(cfgdir):
                return cfgdir
            pathsplit = os.path.split(checkpath)
            # root dir
            if pathsplit[0] == checkpath:
                return ""
            checkpath = pathsplit[0]
            self.relative_path_ = os.path.join(pathsplit[1], self.relative_path_)

        return ""

    def showResult(self, msg):
        #cmdline = 'net send "%s" %s ' % (os.environ['COMPUTERNAME'],msg)
        #p = subprocess.Popen(cmdline)
        print msg

    def execUpload(self, filepath):
        #if len(self.relative_path_) == 0:
        #    self.relative_path_ = '.'
        tofile = '%s:%s/%s' % (self.pscp_cfg_.svrip,
            self.pscp_cfg_.svrbasepath, self.relative_path_)
        tofile = tofile.replace('\\', '/')
        fromfile = filepath
        args = self._get_command(fromfile, tofile)
        # for a in args:
        #     sublime.message_dialog(a)
        sublime.set_timeout(self.listener.show_status(
            'begin upload file, waiting %ds...' % self.pscp_cfg_.timeout), 0)
        self.proc = AsyncProcess(args, None, self.listener)
        self._check_process_finish()
        return True

    def _check_process_finish(self):
        if not self.proc.poll():
            pass
            # self.listener.on_finished(self.proc)
        else:
            est = time.time() - self.proc.start_time
            # self.listener.show_status('time %s , timeout=%d' % (str(est), self.pscp_cfg_.timeout))
            if est > self.pscp_cfg_.timeout:
                self.proc.kill()
                self.listener.show_status('Operation timeout')
            else:
                sublime.set_timeout(self._check_process_finish, 1000)

    def _get_pscp_command_path(self):
        pscp = os.path.join(sublime.packages_path(), 'SublimeSftpSync')
        if sublime.arch() == "x32":
            return os.path.join(pscp, 'bin', 'pscp.exe')
        else:
            return os.path.join(pscp, 'bin', 'pscp64.exe')

    def _get_command(self, fromfile, tofile):
        cmdargs = []
        if sublime.platform() == "windows":
            cmdargs += ['-l', self.pscp_cfg_.svruser, '-P', str(self.pscp_cfg_.svrport)]
            if self.pscp_cfg_.svrkeyfile:
                cmdargs += ['-i', self.self.pscp_cfg_.svrkeyfile]
            elif self.pscp_cfg_.svruserpwd:
                cmdargs += ['-pw', self.pscp_cfg_.svruserpwd]
            else:
                print "server user password or key file has not been specified"
                return False

            if os.path.isdir(fromfile):
                cmdargs = [self._get_pscp_command_path()] + cmdargs
                cmdargs += ['-r', fromfile, tofile]
            else:
                cmdargs = [self._get_pscp_command_path()] + cmdargs
                cmdargs += [fromfile, tofile]

            #cmdline = cmdline.replace('\\','/')
            # sublime.message_dialog(self._get_pscp_command_path())
            return cmdargs
        else:
            # print "tofile : %s" % tofile
            # host = '%s@%s' % (self.pscp_cfg_.svruser, self.pscp_cfg_.svrip)
            cmdargs = ['scp', '-B', '-P', str(self.pscp_cfg_.svrport)]
            if self.pscp_cfg_.svrkeyfile:
                cmdargs += ['-i', self.pscp_cfg_.svrkeyfile]
            if os.path.isdir(fromfile):
                cmdargs += ['-r', fromfile, '%s@%s' % (self.pscp_cfg_.svruser, tofile)]
            else:
                cmdargs += [fromfile, '%s@%s' % (self.pscp_cfg_.svruser, tofile)]
            # cmdline = 'scp -l %s:%d' % (self.pscp_cfg_.svruser, self.pscp_cfg_.svrport)
            print cmdargs
            return cmdargs

        # p = subprocess.Popen(cmdline,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        # ret = p.communicate()
        # if len(ret[0]) == 0:
        #     print "result : %s" % ret[1].strip()
        #     self.showResult(ret[1].strip())
        #     msvcrt.getch()
        #     return False
        # else:
        #     self.showResult('Success [%s]' % os.path.basename(filepath))
        #     return True

    def execDownload(self, filepath):
        pass
        # if len(self.relative_path_) == 0:
        #     self.relative_path_ = '.'
        # isdir = 0
        # if os.path.isdir(filepath):
        #     isdir = 1

        # fromfile = '%s:%s/%s/%s' % (self.pscp_cfg_.svrip,self.pscp_cfg_.svrbasepath,self.relative_path_,os.path.basename(filepath))
        # fromfile = fromfile.replace('\\','/')
        # tofile = os.path.dirname(filepath)
        # if tofile == "":
        #     tofile = "."
        # cmdarg = '-l %s -P %d ' % (self.pscp_cfg_.svruser,self.pscp_cfg_.svrport)
        # if len(self.pscp_cfg_.svrkeyfile) > 0:
        #     cmdarg = '%s -i %s' % (cmdarg , self.pscp_cfg_.svrkeyfile)
        # elif len(self.pscp_cfg_.svruserpwd) > 0:
        #     cmdarg = '%s -pw %s' % (cmdarg , self.pscp_cfg_.svruserpwd)
        # else:
        #     print "server user password or key file has not been specified"
        #     return False

        # if isdir == 1:
        #     cmdline = '%s %s -r %s %s' % (PSCPCMD, cmdarg, fromfile, tofile)
        # else:
        #     cmdline = '%s %s %s %s' % (PSCPCMD, cmdarg, fromfile, tofile)
        # p = subprocess.Popen(cmdline, stdin=subprocess.PIPE,
        #     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # ret = p.communicate()
        # if len(ret[0]) == 0:
        #     print "result : %s" % ret[1].strip()
        #     self.showResult(ret[1].strip())
        #     return False
        # else:
        #     self.showResult('Success [%s]' % os.path.basename(filepath))
        #     return True

    def execute(self, filepath, upload=True):
        if upload:
            return self.execUpload(filepath)
        else:
            return self.execDownload(filepath)

    def transferFile(self, filepath, upload):
        if not os.path.isfile(filepath) and not os.path.isdir(filepath):
            sublime.message_dialog("is not a regular file or directory")
            return False
        dirpath = os.path.realpath(os.path.dirname(filepath))
        view = sublime.active_window().active_view()
        s = view.settings()
        if s.has('sftp_server_ip'):
            # sublime.message_dialog(u"load project config")
            self.pscp_cfg_.svrip = s.get('sftp_server_ip')
            self.pscp_cfg_.svrport = int(s.get('sftp_server_port', '22'))
            self.pscp_cfg_.svruser = s.get('sftp_user', None)
            self.pscp_cfg_.svruserpwd = s.get('sftp_password', None)
            self.pscp_cfg_.svrkeyfile = s.get('sftp_keyfile', None)
            self.pscp_cfg_.svrbasepath = s.get('sftp_basepath', '/')
            self.pscp_cfg_.timeout = int(s.get('sftp_timeout', '10'))
        else:
            cfgfile = self._findCfgForPath(dirpath)
            if len(cfgfile) == 0:
                sublime.message_dialog("no config file found!")
                return False
            self.pscp_cfg_.load_config(cfgfile)
        #print "relative[%s]" % self.relative_path_
        # sublime.message_dialog(u"transfer!!!")
        return self.execute(filepath, upload)
