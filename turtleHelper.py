import sys
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSlot, QThread, pyqtSignal
from PyQt5 import QtGui, QtCore
import PyQt5.sip
import os
import time
import queue
from functools import partial

from PTTLibrary import PTT
from PTTLibrary import Big5uao
from signalCode import SignalCode

VERSION = 'v1.04'

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

Logo = resource_path("turtle.ico")

class Mail():
    def __init__(self, receiver, title, content):
        self.receiver = receiver
        self.title = title
        self.content = content

class Task():
    def __init__(self, name, **kwargs):
        self.name = name
        self.kwargs = kwargs

class PTTThread(QThread):
    msg = pyqtSignal(str)
    signal = pyqtSignal(int)
    progress = pyqtSignal(int)
    ptt_id = ''
    password = ''

    def __init__(self):
        QThread.__init__(self)
        self.queue = queue.Queue()

    def __del__(self):
        self.wait()

    def handleTask(self, task):
        if task.name == 'login':
            self.PTTBot = PTT.Library(self.ptt_id, self.password, False)
            self.pttErrCode = self.PTTBot.login()
            self.PTTBot.Log(self.pttErrCode)
            if self.pttErrCode != PTT.ErrorCode.Success:
                self.msg.emit('登入失敗')
                self.signal.emit(SignalCode.LoginFailed)
                self.PTTBot.Log('登入失敗')

            self.msg.emit('登入成功')
            self.signal.emit(SignalCode.LoginSuccess)
            
            self.PTTBot.Log('登入成功! 準備進行動作...')
        elif task.name == 'sendMails':
            self.sendMails(task.kwargs['mails'], task.kwargs['backup'])
        elif task.name == 'push':
            self.push(task.kwargs['board'], task.kwargs['post_index'], task.kwargs['text'])
        elif task.name == 'editPost':
            self.editPost(task.kwargs['board'], task.kwargs['post_index'], task.kwargs['edit_msg'])

    def run(self):
        while True:
            task = self.queue.get()
            if task == None:
                break
            self.handleTask(task)

    def editPost(self, board, postIndex, msg):
        self.msg.emit('開始編輯文章')
        self.PTTBot.gotoBoard(board)
        self.PTTBot.gotoArticle(postIndex)
        self.PTTBot.editArticle(msg)
        self.msg.emit('編輯文章成功')

    def sendMails(self, mails, backup):
        self.progress.emit(0)
        
        idx = 0
        for m in mails:
            self.send(m.receiver, m.title, m.content, backup)
            idx += 1
            self.progress.emit(idx)

    def send(self, id, title, content, backup):
        self.msg.emit('準備寄信給' + id)
        self.pttErrCode = self.PTTBot.mail(id, title, content, 0, backup)
        if self.pttErrCode == PTT.ErrorCode.Success:
            self.PTTBot.Log('寄信給 ' + id + ' 成功')
            self.msg.emit('寄信給 ' + id + ' 成功')
        else:
            self.PTTBot.Log('寄信給 ' + id + ' 失敗')
            self.msg.emit('寄信給 ' + id + ' 失敗')
    
    def push(self, board, post_index, content):
        self.msg.emit('準備推文')
        self.pttErrCode = self.PTTBot.push(board, PTT.PushType.Push, content, PostIndex=post_index)
        if self.pttErrCode == PTT.ErrorCode.Success:
            self.msg.emit('推文成功')
        elif self.pttErrCode == PTT.ErrorCode.ErrorInput:
            self.msg.emit('使用文章編號: 參數錯誤')
        elif self.pttErrCode == PTT.ErrorCode.NoPermission:
            self.msg.emit('使用文章編號: 無發文權限')
        else:
            self.msg.emit('使用文章編號: 推文失敗')
        self.signal.emit(SignalCode.PushComplete)
 
# pip install pyinstaller
# pyinstaller pttHelper.spec
class App(QMainWindow):
 
    def __init__(self):
        super().__init__()

        self._ptt = PTTThread()
        self._ptt.msg.connect(self.getMsg)
        self._ptt.signal.connect(self.getSignal)
        self._ptt.progress.connect(self.getProgress)
        self._ptt.start()

        self.initUI()
 
        
    def initUI(self):
        self.title = '海龜小幫手 ' + VERSION
        self.setWindowIcon(QtGui.QIcon(Logo))
        self.setWindowTitle(self.title)
        self.central_widget = QStackedWidget()
        self.setCentralWidget(self.central_widget)

        self.widget = Login(self)
        self.widget.login_button.clicked.connect(self.login)
        self.central_widget.addWidget(self.widget)
        self.central_widget.setCurrentWidget(self.widget)
        self.show()

    def login(self):
        # self.toMainWidget()
        self.statusBar().showMessage('登入中')
        self.widget.account_input.setDisabled(True)
        self.widget.password_input.setDisabled(True)
        self.widget.login_button.setDisabled(True)
        self._ptt.ptt_id = self.widget.account_input.text()
        self._ptt.password = self.widget.password_input.text()
        self._ptt.queue.put(Task('login'))
        
    def toMainWidget(self):
        self.widget = MainWidget(self)
        self.central_widget.addWidget(self.widget)
        self.central_widget.setCurrentWidget(self.widget)
        # connect events
        self.widget.send_button.clicked.connect(self.sendMails)
        self.widget.preview_button.clicked.connect(self.previewMail)
        for i in range(len(self.widget.quickPushFormButtons)):
            self.widget.quickPushFormButtons[i].clicked.connect(partial(self.push, i))
        self.widget.edit_content_button.clicked.connect(self.edit_post)
        self.resize(600, 20)

    def edit_post(self):
        board = self.widget.board_input.text()
        post_index = int(self.widget.post_index_input.text())
        edit_msg = self.widget.edit_content_input.toPlainText().replace('\n', '\r')
        if len(edit_msg) > 0:
            self._ptt.queue.put(Task('editPost', edit_msg = edit_msg, post_index=post_index, board=board))
        else:
            self.statusBar().showMessage('失敗, 推文內容為空白')

    def push(self, i):
        board = self.widget.board_input.text()
        post_index = int(self.widget.post_index_input.text())
        push_text = self.widget.quickPushFormControls[i].text()
        if len(push_text) > 0:
            self.widget.quickPushFormButtons[i].setEnabled(False)
            self._ptt.queue.put(Task('push', text = push_text, post_index=post_index, board=board))
        else:
            self.statusBar().showMessage('失敗, 推文內容為空白')

    def createMails(self):
        receivers = self.widget.receivers_input.text()
        commands = self.widget.commands_input.text()
        titles = self.widget.title_input.text()
        content = self.widget.content_input.toPlainText()

        receiver_list = receivers.split('@')
        title_list = titles.split('@')
        command_list = commands.split('@')

        mail_list = []

        idx = 0
        for r in receiver_list:
            title = title_list[-1]
            if len(title_list) > idx + 1:
                title = title_list[idx]
            
            command = command_list[-1]
            if len(command_list) > idx + 1:
                command = command_list[idx]
            
            c = content.replace('[指令]', command).replace('\n', '\r')

            mail_list.append(Mail(r, title, c))
            idx += 1
        
        return mail_list


    def sendMails(self):
        save_backup = self.widget.backup_input.isChecked()
        
        mails = self.createMails()
        self.widget.progressbar.setMaximum(len(mails))
        self._ptt.queue.put(Task('sendMails', mails = mails, backup = save_backup))
    
    def createPreviewContent(self, mail):
        content = '收件人:\t'+mail.receiver+'\r'\
        + '標題  :\t'+mail.title+'\r'\
        + '內文  :\r\r' + mail.content
        return content

    def viewNextMail(self):
        mails = self.createMails()
        self.view_mail_index = (self.view_mail_index + 1) % len(mails)
        self.d_title_label.setText('正在檢視第' + str(self.view_mail_index + 1) + '/' + str(len(mails)) + '封')
        self.d_content_label.setText(self.createPreviewContent(mails[self.view_mail_index]))

    def closeDialogAndSendMails(self):
        self.d.close()
        self.sendMails()

    def previewMail(self):
        self.d = QDialog()
        self.d.setWindowTitle('郵件預覽')
        self.d.setWindowIcon(QtGui.QIcon(Logo))
        self.view_mail_index = 0
        mails = self.createMails()

        form_layout = QFormLayout()
        self.d_title_label = QLabel('正在檢視第' + str(self.view_mail_index + 1) + '/' + str(len(mails)) + '封')
        self.d_content_label = QTextEdit()
        self.d_content_label.setText(self.createPreviewContent(mails[self.view_mail_index]))
        self.d_content_label.setReadOnly(True)
        
        send_mail = QPushButton('寄信')
        next_button = QPushButton('預覽下一封')
        send_mail.clicked.connect(self.closeDialogAndSendMails)
        next_button.clicked.connect(self.viewNextMail)

        if len(mails) == 1:
            next_button.setDisabled(True)

        form_layout.addRow(self.d_title_label)
        form_layout.addRow(self.d_content_label)
        form_layout.addRow(send_mail, next_button)
        self.d.setLayout(form_layout)
        
        self.d.setGeometry(self.geometry().x(), self.geometry().y(), self.d.width(), self.d.height())

        self.d.exec_()

    def getProgress(self, progress):
        self.widget.progressbar.setValue(progress)

    def getMsg(self, msg):
        self.statusBar().showMessage(msg)

    def getSignal(self, signal):
        if (signal == SignalCode.LoginFailed):
            self.widget.account_input.setEnabled(True)
            self.widget.password_input.setEnabled(True)
            self.widget.login_button.setEnabled(True)

        elif (signal == SignalCode.LoginSuccess):
            self.toMainWidget()

        elif (signal == SignalCode.PushComplete):
            for button in self.widget.quickPushFormButtons:
                button.setEnabled(True)


class Login(QWidget):        
 
    def __init__(self, parent):   
        super(QWidget, self).__init__(parent)

        self.layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        
        self.account_label = QLabel('Account')
        self.account_input = QLineEdit()
        self.account_input.setPlaceholderText('PTT Account')

        self.password_label = QLabel('Password')
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText('PTT Password')
        self.password_input.setEchoMode(QLineEdit.Password)

        self.login_button = QPushButton('登入')

        form_layout.addRow(self.account_label, self.account_input)
        form_layout.addRow(self.password_label, self.password_input)
        form_layout.addRow(self.login_button)
 
        self.layout.addLayout(form_layout)

class MainWidget(QWidget):        
 
    def __init__(self, parent):   
        super(QWidget, self).__init__(parent)

        self.layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.mail_tab = QWidget()	
        self.push_tab = QWidget()
        
        # Add tabs
        self.tabs.addTab(self.mail_tab,"海龜郵差")
        self.tabs.addTab(self.push_tab,"推文幫手")

        self.createMailUI()
        self.createPushUI()

        self.layout.addWidget(self.tabs)

    def createPushUI(self):
        self.push_tab.layout = QVBoxLayout(self)

        v_box = QVBoxLayout()
        form_layout = QFormLayout()
        
        self.board_label = QLabel('看板')
        self.board_input = QLineEdit('turtlesoup')
        
        self.post_index_label = QLabel('文章編號')
        self.post_index_input = QLineEdit()

        form_layout.addRow(self.board_label, self.board_input)
        form_layout.addRow(self.post_index_label, self.post_index_input)

        board_info_group = QGroupBox('看板、文章設定')
        board_info_group.setLayout(form_layout)

        ## 建立快速推文區塊

        fast_push_grid = QGridLayout()
        fast_push_grid.setColumnStretch(0, 0)
        fast_push_grid.setColumnStretch(1, 4)
        fast_push_grid.setColumnStretch(2, 0)

        self.quickPushFormControls = []
        self.quickPushFormButtons = []

        for i in range(5):
            push_label = QLabel('快速推文' + str(i+1))
            push_input = QLineEdit()
            push_input.setPlaceholderText('推文內容')
            push_button = QPushButton('推文' + str(i+1))
            self.quickPushFormControls.append(push_input)
            self.quickPushFormButtons.append(push_button)
            form_layout.addRow(push_label, push_input)
            form_layout.addRow(push_button)
            fast_push_grid.addWidget(push_label, i, 0)
            fast_push_grid.addWidget(push_input, i, 1)
            fast_push_grid.addWidget(push_button, i, 2)
        
        fase_push_group = QGroupBox('快速推文')
        fase_push_group.setLayout(fast_push_grid)

        edit_post_form = QFormLayout()

        # self.push_content_label = QLabel('連續推文')
        # self.push_content_input = QTextEdit()
        # self.push_content_input.setPlaceholderText('不同行會是不同推文')
        # self.push_content_button = QPushButton('連續推文')

        self.edit_content_label = QLabel('底部修文')
        self.edit_content_input = QTextEdit()
        self.edit_content_input.setPlaceholderText('底部修文內容')
        self.edit_content_button = QPushButton('修文')

        # edit_post_form.addRow(self.push_content_label, self.push_content_input)
        # edit_post_form.addRow(self.push_content_button)
        edit_post_form.addRow(self.edit_content_label, self.edit_content_input)
        edit_post_form.addRow(self.edit_content_button)

        edit_post_group = QGroupBox('底部修文')
        edit_post_group.setLayout(edit_post_form)

        v_box.addWidget(board_info_group)
        v_box.addWidget(fase_push_group)
        v_box.addWidget(edit_post_group)
        v_box.addStretch()
        # self.push_tab.layout.addWidget(form_layout2)
        self.push_tab.setLayout(v_box)

    
    def createMailUI(self):
        # create ui for mail tab
        self.mail_tab.layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        self.receivers_label = QLabel('收件人')
        self.receivers_input = QLineEdit()
        self.receivers_input.setPlaceholderText('可用@號分隔收件人')

        self.commands_label = QLabel('指令')
        self.commands_input = QLineEdit()
        self.commands_input.setPlaceholderText('會取代掉內文的[指令], 以@號分隔')

        self.title_label = QLabel('標題')
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText('可用@號分隔不同收件人收到的標題')

        self.content_label = QLabel('內文')
        self.content_input = QTextEdit()

        self.backup_input = QCheckBox('是否儲存底稿')
        
        self.progressbar = QProgressBar()

        self.send_button = QPushButton('寄信')
        self.preview_button = QPushButton('預覽')

        form_layout.addRow(self.receivers_label, self.receivers_input)
        form_layout.addRow(self.commands_label, self.commands_input)
        form_layout.addRow(self.title_label, self.title_input)
        form_layout.addRow(self.content_label, self.content_input)
        form_layout.addRow(self.backup_input)
        form_layout.addRow(self.progressbar)
        form_layout.addRow(self.send_button, self.preview_button)

        self.mail_tab.setLayout(form_layout)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    app.setStyle('Fusion')
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(53,53,53))
    palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(15,15,15))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(53,53,53))
    palette.setColor(QtGui.QPalette.ToolTipBase, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.ToolTipText, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(53,53,53))
    palette.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
         
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(142,45,197).lighter())
    palette.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.black)
    app.setPalette(palette)

    ex = App()
    sys.exit(app.exec_())