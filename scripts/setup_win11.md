# Windows 11 定时任务设置指南

## 方式一：自动设置脚本（推荐）

### 步骤

1. **以管理员身份运行 PowerShell**

   右键点击开始按钮 → 选择 "终端(管理员)" 或 "Windows PowerShell(管理员)"

2. **进入项目目录**
   ```powershell
   cd D:\privategit\github\stockScience
   ```

3. **执行设置脚本**
   ```powershell
   .\scripts\setup_scheduled_task.bat
   ```

4. **验证任务创建**
   ```powershell
   schtasks /query /tn StockScience_DailyScreens
   ```

---

## 方式二：手动在任务计划程序中创建

### 步骤

1. **打开任务计划程序**

   - 按 `Win + R`，输入 `taskschd.msc`，回车
   - 或：开始菜单 → Windows 工具 → 任务计划程序

2. **创建基本任务**

   - 右侧点击 "创建基本任务"
   - 名称: `StockScience_DailyScreens`
   - 点击 "下一步"

3. **设置触发器**

   - 选择: "每周"
   - 点击 "下一步"
   - 勾选: 周一、周二、周三、周四、周五
   - 开始时间: `21:00:00`
   - 点击 "下一步"

4. **设置操作**

   - 选择: "启动程序"
   - 点击 "下一步"
   - 程序或脚本: `D:\privategit\github\stockScience\.venv\Scripts\python.exe`
   - 添加参数: `D:\privategit\github\stockScience\scripts\run_daily_screens.py`
   - 起始于: `D:\privategit\github\stockScience`
   - 点击 "下一步"

5. **完成**

   - 勾选 "打开此任务属性的对话框"
   - 点击 "完成"

6. **高级设置**（属性窗口中）

   - 常规选项卡:
     - ✅ 不管用户是否登录都要运行
     - ✅ 使用最高权限运行

   - 条件选项卡:
     - ❌ 取消 "只有在计算机使用交流电源时才启动此任务"

   - 设置选项卡:
     - ✅ 如果任务失败，按以下频率重新启动: 5分钟
     - 尝试重新启动: 3次

---

## 测试执行

### 手动测试
```powershell
cd D:\privategit\github\stockScience
.\scripts\test_daily_screens.bat
```

### 立即运行任务
```powershell
schtasks /run /tn StockScience_DailyScreens
```

---

## 查看日志

```powershell
# 查看今天的日志
notepad logs\daily_screen_[日期].log

# 或在 PowerShell 中实时查看
Get-Content logs\daily_screen_*.log -Tail 50 -Wait
```

---

## 常见问题

### 1. Python 路径错误

修改 `setup_scheduled_task.bat` 中的 Python 路径：
```batch
set "PYTHON_EXE=D:\你的Python路径\python.exe"
```

或使用虚拟环境：
```batch
set "PYTHON_EXE=D:\privategit\github\stockScience\.venv\Scripts\python.exe"
```

### 2. 权限不足

必须以**管理员身份**运行设置脚本

### 3. 删除任务

```powershell
schtasks /delete /tn StockScience_DailyScreens /f
```

---

## 定时时间修改

如需修改执行时间，在任务计划程序中：
1. 找到 `StockScience_DailyScreens` 任务
2. 右键 → 属性 → 触发器
3. 编辑触发器，修改时间
