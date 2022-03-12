import sys
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QIcon, QKeySequence, QPalette, QColor
from PyQt5.QtCore import pyqtSlot, QThread, pyqtSignal, QSettings, Qt
from PyQt5 import QtGui, QtCore
import PyQt5.sip
import os
import time
import queue
from functools import partial

from PyPtt import PTT

LoginSuccess = 1
LoginFailed = 2
PushComplete = 3

VERSION = 'v1.17.4'

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
    def __init__(self, receiver, title, sign_file, content):
        self.receiver = receiver
        self.sign_file = sign_file
        self.title = title
        self.content = content

class Task():
    def __init__(self, name, **kwargs):
        self.name = name
        self.kwargs = kwargs

class PTTThread(QThread):
    msg = pyqtSignal(str)
    signal = pyqtSignal(int)
    log_msg_signal = pyqtSignal(str)
    progress = pyqtSignal(int)
    ptt_id = ''
    password = ''
    enable_trace = False
    logs = []

    def __init__(self):
        QThread.__init__(self)
        self.queue = queue.Queue()

    def __del__(self):
        self.wait()

    def handleTask(self, task):
        if task.name == 'login':
            level = PTT.log.level.INFO
            if self.enable_trace:
                level = PTT.log.level.TRACE
            self.ptt_bot = PTT.API(log_handler=self.logHandler, log_level=level)
            try:
                self.ptt_bot.login(self.ptt_id, self.password)
                self.msg.emit('登入成功')
                self.signal.emit(LoginSuccess)
            except:
                self.signal.emit(LoginFailed)
                self.msg.emit('登入失敗')
        elif task.name == 'push':
            self.push(task.kwargs['board'], task.kwargs['post_index'], task.kwargs['text'])
        elif task.name == 'sendMails':
            self.sendMails(task.kwargs['mails'], task.kwargs['backup'])
        elif task.name == 'editPost':
            self.editPost(task.kwargs['board'], task.kwargs['post_index'], task.kwargs['edit_msg'])
        elif task.name == 'changeLoglevel':
            self.setLogLevelToTrace(task.kwargs['toTrace'])
        elif task.name == 'giveMoney':
            self.giveMoney(
                task.kwargs['amount'],
                task.kwargs['receivers'],
                task.kwargs['edit_bag'],
                task.kwargs['bag_title'],
                task.kwargs['bag_content']
                )
        elif task.name == 'giveDifferentMoney':
            self.giveDifferentMoney(
                task.kwargs['receivers_and_amount'],
                task.kwargs['edit_bag'],
                task.kwargs['bag_title'],
                task.kwargs['bag_content']
                )

    def logHandler(self, msg):
        self.log_msg_signal.emit(msg)

    def setLogLevelToTrace(self, toTrace):
        if toTrace:
            self.ptt_bot.log("set log level to trace")
            self.ptt_bot.log_level = PTT.log.level.TRACE
        else:
            self.ptt_bot.log("set log level to info")
            self.ptt_bot.log_level = PTT.log.level.INFO

    def run(self):
        while True:
            task = self.queue.get()
            if task == None:
                break
            self.handleTask(task)

    def giveDifferentMoney(self, receivers_and_amount, edit_bag, title, content):
        self.progress.emit(0)
        idx = 0
        for id_and_amount in receivers_and_amount:
            try:
                id = id_and_amount.split(':')[0]
                amount = int(id_and_amount.split(':')[1])
                self.ptt_bot.log('準備發錢給' + id + ' 共' + str(amount))

                self.pttErrCode = self.ptt_bot.give_money(id, int(amount), title, content)
                self.ptt_bot.log('發錢給 ' + id + ' 成功')
                self.msg.emit('發錢給 ' + id + ' 成功')
            except Exception as e:
                self.ptt_bot.log(str(e))
                self.ptt_bot.log('發錢給 ' + id + ' 失敗')
                self.msg.emit('發錢給 ' + id + ' 不明原因失敗')

            idx += 1
            self.progress.emit(idx)

    def giveMoney(self, amount, receivers, edit_bag, title, content):
        self.progress.emit(0)
        idx = 0
        for id in receivers:
            self.ptt_bot.log('準備發錢給' + id)
            try:
                self.pttErrCode = self.ptt_bot.give_money(id, int(amount), title, content)
                self.ptt_bot.log('發錢給 ' + id + ' 成功')
                self.msg.emit('發錢給 ' + id + ' 成功')
            except Exception as e:
                self.ptt_bot.log(str(e))
                self.ptt_bot.log('發錢給 ' + id + ' 失敗')
                self.msg.emit('發錢給 ' + id + ' 不明原因失敗')

            idx += 1
            self.progress.emit(idx)

    def sendMails(self, mails, backup):
        self.progress.emit(0)
        idx = 0
        for m in mails:
            self.send(m.receiver, m.title, m.content, m.sign_file, backup)
            idx += 1
            self.progress.emit(idx)

    def send(self, id, title, content, sign_file, backup):
        self.msg.emit('準備寄信給' + id)
        try:
            self.pttErrCode = self.ptt_bot.mail(id, title, content, sign_file, backup)
            self.ptt_bot.log('寄信給 ' + id + ' 成功')
            self.msg.emit('寄信給 ' + id + ' 成功')
        except:
            self.ptt_bot.log('寄信給 ' + id + ' 失敗')
            self.msg.emit('寄信給 ' + id + ' 不明原因失敗')
    
    def push(self, board, post_index, content):
        self.msg.emit('準備推文')
        try:
            self.ptt_bot.push(board, PTT.data_type.push_type.PUSH, content, post_index=post_index)
            self.msg.emit('推文成功')
        except:
            self.msg.emit('推文失敗: 可能文章過長 無法連續推文 或其他奇奇怪怪的因素')
 
# pip install pyinstaller
# pyinstaller turtleHelper.spec
class App(QMainWindow):
 
    def __init__(self):
        super().__init__()

        self._ptt = PTTThread()
        self._ptt.msg.connect(self.getMsg)
        self._ptt.log_msg_signal.connect(self.getLog)
        self._ptt.signal.connect(self.getSignal)
        self._ptt.progress.connect(self.getProgress)
        self._ptt.start()
        self.main_widget_init = False
        self.logs = []
        self.settings = QSettings('Turtle', 'helper')

        self.initUI()
 
        
    def initUI(self):
        self.title = '海龜小幫手 ' + VERSION
        self.setWindowIcon(QtGui.QIcon(Logo))
        self.setWindowTitle(self.title)
        self.central_widget = QStackedWidget()
        self.setCentralWidget(self.central_widget)
        self.widget = Login(self)
        self.widget.password_input.returnPressed.connect(self.login)
        self.widget.login_button.clicked.connect(self.login)
        self.central_widget.addWidget(self.widget)
        self.central_widget.setCurrentWidget(self.widget)
        self.widget.account_input.setText(self.settings.value('id'))
        self.show()

    def login(self):
        # self.toMainWidget()
        self.statusBar().showMessage('登入中')
        self.widget.account_input.setDisabled(True)
        self.widget.password_input.setDisabled(True)
        self.widget.login_button.setDisabled(True)
        self._ptt.ptt_id = self.widget.account_input.text()
        self.settings.setValue('id', self._ptt.ptt_id) 
        self._ptt.password = self.widget.password_input.text()
        self._ptt.enable_trace = self.widget.enable_trace.isChecked()
        self._ptt.queue.put(Task('login'))
        
    def toMainWidget(self):
        self.widget = MainWidget(self)
        self.central_widget.addWidget(self.widget)
        self.central_widget.setCurrentWidget(self.widget)
        # connect events
        self.widget.send_button.clicked.connect(self.sendMails)
        self.widget.preview_button.clicked.connect(self.previewMail)
        for i in range(len(self.widget.quickPushFormButtons)):
            self.widget.quickPushFormButtons[i].clicked.connect(partial(self.push, i, False))
            self.widget.quickPushFormControls[i].returnPressed.connect(partial(self.push, i, True))
        self.widget.multi_line_push_button.clicked.connect(self.multi_line_push)
        self.widget.send_money_button.clicked.connect(self.sendMoney)
        self.widget.send_different_money_button.clicked.connect(self.sendMoneyDifferent)
        self.resize(600, 20)
        self.main_widget_init = True
        self.updateLogs()

    def multi_line_push(self):
        board = self.widget.board_input.text()
        post_index = int(self.widget.post_index_input.text())
        msgs = self.widget.multi_line_push_input.toPlainText().split('\n')
        self.statusBar().showMessage('推文中')
        try:
            for m in msgs:
                self._ptt.queue.put(Task('push', text = m, post_index=post_index, board=board))
        except:
            self.statusBar().showMessage('推文失敗, 不明原因')    
        self.statusBar().showMessage('推文成功')

    def push(self, i, byEnter):
        if byEnter and not self.widget.enablePushOnEnterCheckbox.isChecked():
            return
        board = self.widget.board_input.text()
        post_index = int(self.widget.post_index_input.text())
        push_text = self.widget.quickPushFormControls[i].text()
        if self.widget.clearTextAfterPushCheckbox.isChecked():
            self.widget.quickPushFormControls[i].setText('')
        if len(push_text) > 0:
            self.widget.quickPushFormButtons[i].setEnabled(False)
            self._ptt.queue.put(Task('push', text = push_text, post_index=post_index, board=board))
        else:
            self.statusBar().showMessage('失敗, 推文內容為空白')

    def createMails(self):
        receivers = self.widget.receivers_input.text()
        commands = self.widget.commands_input.text()
        titles = self.widget.title_input.text()
        sign_file = self.widget.sign_file_input.text()
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

            mail_list.append(Mail(r, title, sign_file, c))
            idx += 1
        
        return mail_list

    def sendMails(self):
        save_backup = self.widget.backup_input.isChecked()
        
        mails = self.createMails()
        self.widget.progressbar.setMaximum(len(mails))
        self._ptt.queue.put(Task('sendMails', mails = mails, backup = save_backup))
    
    def sendMoney(self):
        amount = self.widget.money_amount_input.text()
        edit_bag = self.widget.edit_red_bag_checkbox.isChecked()
        bag_title = self.widget.edit_red_bag_title_input.text()
        bag_content = self.widget.edit_red_bag_content_input.toPlainText().replace('\n', '\r\n')

        receivers = self.widget.money_receivers_input.toPlainText().split('\n')
        receivers = list(filter(None, receivers))
        self.widget.progressbar.setMaximum(len(receivers))
        self.statusBar().showMessage('發錢中')
        try:
            self._ptt.queue.put(Task(
                'giveMoney',
                amount=amount,
                receivers=receivers,
                edit_bag=edit_bag,
                bag_title=bag_title,
                bag_content=bag_content))
        except Exception as e:
            self.statusBar().showMessage('發錢失敗, 不明原因')  

    def sendMoneyDifferent(self):
        receivers_and_amount = self.widget.money_receivers_amount_input.toPlainText().split('\n')
        receivers_and_amount = list(filter(None, receivers_and_amount))
        edit_bag = self.widget.edit_red_bag_checkbox.isChecked()
        bag_title = self.widget.edit_red_bag_title_input.text()
        bag_content = self.widget.edit_red_bag_content_input.toPlainText().replace('\n', '\r\n')
        self.widget.progressbar.setMaximum(len(receivers_and_amount))
        self.statusBar().showMessage('發錢中')
        try:
            self._ptt.queue.put(Task('giveDifferentMoney', 
                receivers_and_amount=receivers_and_amount,
                edit_bag=edit_bag,
                bag_title=bag_title,
                bag_content=bag_content))
        except Exception as e:
            self.statusBar().showMessage('發錢失敗, 不明原因')  

    
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

    def updateLogs(self):
        if self.main_widget_init:
            self.widget.logs_display.setText('\n'.join(self.logs))
            self.widget.logs_display.moveCursor(QtGui.QTextCursor.End)

    def getLog(self, msg):
        self.logs.append(msg)
        if len(self.logs) >= 150 :
            self.logs.pop(0)
        self.updateLogs()


    def getSignal(self, signal):
        if (signal == LoginFailed):
            self.widget.account_input.setEnabled(True)
            self.widget.password_input.setEnabled(True)
            self.widget.login_button.setEnabled(True)

        elif (signal == LoginSuccess):
            self.toMainWidget()

        elif (signal == PushComplete):
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
        self.enable_trace = QCheckBox('啟用Trace')

        self.password_label = QLabel('Password')
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText('PTT Password')
        self.password_input.setEchoMode(QLineEdit.Password)

        self.login_button = QPushButton('登入')

        form_layout.addRow(self.account_label, self.account_input)
        form_layout.addRow(self.password_label, self.password_input)
        form_layout.addRow(self.enable_trace)
        form_layout.addRow(self.login_button)
 
        self.layout.addLayout(form_layout)

class MainWidget(QWidget):
    
    def __init__(self, parent):
        super(QWidget, self).__init__(parent)

        self.layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.mail_tab = QWidget()	
        self.push_tab = QWidget()
        self.give_money_tab = QWidget()

        self.logs_display = QTextEdit()
        self.logs_display.setReadOnly(True)
        
        # Add tabs
        self.tabs.addTab(self.mail_tab,"海龜郵差")
        self.tabs.addTab(self.push_tab,"推文幫手")
        self.tabs.addTab(self.give_money_tab,"噴錢槍")

        self.createMailUI()
        self.createPushUI()
        self.createGiveMoneyUI()

        self.layout.addWidget(self.tabs)
        self.layout.addWidget(self.logs_display)

    def createGiveMoneyUI(self):
        self.give_money_tab.layout = QVBoxLayout(self)
        v_box = QVBoxLayout()

        # 紅包袋
        edit_bag_group = QGroupBox('修改紅包袋')
        edit_bag_form = QFormLayout()
        self.edit_red_bag_checkbox = QCheckBox('是否修改紅包袋')
        self.edit_red_bag_title_label = QLabel('紅包袋標題')
        self.edit_red_bag_title_input = QLineEdit()
        self.edit_red_bag_content_label = QLabel('紅包袋內文')
        self.edit_red_bag_content_input = QTextEdit()
        
        edit_bag_form.addRow(self.edit_red_bag_checkbox)
        edit_bag_form.addRow(self.edit_red_bag_title_label, self.edit_red_bag_title_input)
        edit_bag_form.addRow(self.edit_red_bag_content_label, self.edit_red_bag_content_input)

        edit_bag_group.setLayout(edit_bag_form)
        
        # 定額
        fixed_give_money_group = QGroupBox('定額發錢(每個人收到一樣的金額)')
        fixed_money_form = QFormLayout()
        self.money_amount_label = QLabel('金額(是稅後喔!!)')
        self.money_amount_input = QLineEdit('')

        self.money_receivers_label = QLabel('收款人(以換行分隔)')
        self.money_receivers_input = QTextEdit()

        self.send_money_button = QPushButton('發錢')

        fixed_money_form.addRow(self.money_amount_label, self.money_amount_input)
        fixed_money_form.addRow(self.money_receivers_label, self.money_receivers_input)
        fixed_money_form.addRow(self.send_money_button)

        fixed_give_money_group.setLayout(fixed_money_form)
        # 定額END

        different_give_money_group = QGroupBox('非定額發錢 (每個人收到不一樣的金額)')
        different_money_form = QFormLayout()
        self.money_receivers_amount_label = QLabel('收款人+金額(以換行分隔 也是稅後喔!!)')
        self.money_receivers_amount_input = QTextEdit()
        self.money_receivers_amount_input.setPlaceholderText('id:金額\nid:金額\nid:金額')
        self.send_different_money_button = QPushButton('發錢')

        different_money_form.addRow(self.money_receivers_amount_label, self.money_receivers_amount_input)
        different_money_form.addRow(self.send_different_money_button)

        different_give_money_group.setLayout(different_money_form)


        v_box.addWidget(edit_bag_group)
        v_box.addWidget(fixed_give_money_group)
        v_box.addWidget(different_give_money_group)
        self.give_money_tab.setLayout(v_box)

    def createPushUI(self):
        self.push_tab.layout = QVBoxLayout(self)

        v_box = QVBoxLayout()
        form_layout = QFormLayout()
        
        self.board_label = QLabel('看板')
        self.board_input = QLineEdit('turtlesoup')
        
        self.post_index_label = QLabel('文章編號')
        self.post_index_input = QLineEdit('')

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

        self.enablePushOnEnterCheckbox = QCheckBox('是否啟用enter送出推文')
        self.clearTextAfterPushCheckbox = QCheckBox('推文後是否清空文字框')

        fast_push_grid.addWidget(self.enablePushOnEnterCheckbox, 0, 0)
        fast_push_grid.addWidget(self.clearTextAfterPushCheckbox, 1, 0)

        for i in range(5):
            push_label = QLabel('快速推文' + str(i+1))
            push_input = QLineEdit()
            push_input.setPlaceholderText('推文內容')
            push_button = QPushButton('推文' + str(i+1))
            self.quickPushFormControls.append(push_input)
            self.quickPushFormButtons.append(push_button)
            form_layout.addRow(push_label, push_input)
            form_layout.addRow(push_button)
            fast_push_grid.addWidget(push_label, i + 2, 0)
            fast_push_grid.addWidget(push_input, i + 2, 1)
            fast_push_grid.addWidget(push_button, i + 2, 2)
        
        fase_push_group = QGroupBox('快速推文')
        fase_push_group.setLayout(fast_push_grid)

        # 連續推文
        multi_line_push_form = QFormLayout()
        self.multi_line_push_label = QLabel('連續推文')
        self.multi_line_push_input = QTextEdit()
        self.multi_line_push_input.setPlaceholderText('連續推文內容')
        self.multi_line_push_button = QPushButton('推文')

        multi_line_push_form.addRow(self.multi_line_push_label, self.multi_line_push_input)
        multi_line_push_form.addRow(self.multi_line_push_button)

        multi_line_push_group = QGroupBox('連續推文(以換行分開)')
        multi_line_push_group.setLayout(multi_line_push_form)


        # end 連續推文

        edit_post_form = QFormLayout()

        self.edit_content_label = QLabel('底部修文')
        self.edit_content_input = QTextEdit()

        v_box.addWidget(board_info_group)
        v_box.addWidget(fase_push_group)
        v_box.addWidget(multi_line_push_group)
        v_box.addStretch()
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

        self.sign_file_label = QLabel('簽名檔')
        self.sign_file_input = QLineEdit('0')
        self.sign_file_input.setPlaceholderText('0 = 不選簽名檔 請用數字[1-9]')

        self.content_label = QLabel('內文')
        self.content_input = QTextEdit()

        self.backup_input = QCheckBox('是否儲存底稿')
        
        self.progressbar = QProgressBar()

        self.send_button = QPushButton('寄信')
        self.preview_button = QPushButton('預覽')

        form_layout.addRow(self.receivers_label, self.receivers_input)
        form_layout.addRow(self.commands_label, self.commands_input)
        form_layout.addRow(self.title_label, self.title_input)
        form_layout.addRow(self.sign_file_label, self.sign_file_input)
        form_layout.addRow(self.content_label, self.content_input)
        form_layout.addRow(self.backup_input)
        form_layout.addRow(self.progressbar)
        form_layout.addRow(self.send_button, self.preview_button)

        self.mail_tab.setLayout(form_layout)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    app.setStyle('Fusion')
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.WindowText, Qt.white)
    palette.setColor(QtGui.QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QtGui.QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.ToolTipBase, Qt.white)
    palette.setColor(QtGui.QPalette.ToolTipText, Qt.white)
    palette.setColor(QtGui.QPalette.Text, Qt.white)
    palette.setColor(QtGui.QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.ButtonText, Qt.white)
    palette.setColor(QtGui.QPalette.BrightText, Qt.red)
    palette.setColor(QtGui.QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QtGui.QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QtGui.QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)

    ex = App()
    sys.exit(app.exec_())