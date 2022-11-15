###### 本專案透過PTT Library開發，希望可以由機器人輔助各種海龜板的遊戲

## 安裝
-------------------
```
pip3 install -r requirements.txt
```

若需要直接安裝master branch上的最新版可以使用這個指令
```
pip3 install https://github.com/PttCodingMan/PyPtt@master
```


## 執行
-------------------
```
python turtleHelper.py
```


## 功能
- 輔助寄信
- 輔助推文
- 輔助底部修文
- 發錢

![登入畫面](/screenshots/001.png "登入畫面")

![海龜郵差](/screenshots/002.png "海龜郵差")

![推文幫手](/screenshots/003.png "推文幫手")


## 建置
-------------------
需更改 _turtleHelper.spec_ 中的專案路徑
```
pyinstaller turtleHelper.spec
```

自動發布版本
```
git tag -a v1.17.5 -m "new version 1.17.5" 
git push origin --tags
```

需求
-------------------
###### Python 3.10

