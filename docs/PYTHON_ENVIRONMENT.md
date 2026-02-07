# Python环境配置

## 默认Python解释器

本项目使用 **Anaconda base 环境** 的Python解释器：

```
D:\ProgramData\anaconda3\python.exe
```

## 运行Python脚本

### 方法1：使用完整路径（推荐）

```cmd
D:\ProgramData\anaconda3\python.exe your_script.py
```

### 方法2：使用cmd

```cmd
cmd /c "cd /d D:\privategit\github\stockScience && D:\ProgramData\anaconda3\python.exe your_script.py"
```

### 方法3：使用PowerShell

```powershell
& "D:\ProgramData\anaconda3\python.exe" your_script.py
```

## Claude Code Bash工具配置

当使用Bash工具运行Python时，请使用以下格式：

```bash
# cmd格式（首选）
cmd /c "cd /d D:\privategit\github\stockScience && D:\ProgramData\anaconda3\python.exe script.py"

# PowerShell格式（备用）
powershell -Command "Set-Location 'D:\privategit\github\stockScience'; & 'D:\ProgramData\anaconda3\python.exe' script.py"
```

## 验证Python环境

运行以下命令验证环境：

```cmd
D:\ProgramData\anaconda3\python.exe --version
D:\ProgramData\anaconda3\python.exe -c "import sys; print(sys.executable)"
```

预期输出：
```
Python 3.x.x
D:\ProgramData\anaconda3\python.exe
```

## 项目依赖安装

使用Anaconda Python安装依赖：

```cmd
D:\ProgramData\anaconda3\python.exe -m pip install -r requirements.txt
D:\ProgramData\anaconda3\python.exe -m pip install gm  # 掘金SDK
```

## 常用命令示例

### 运行策略脚本
```cmd
cd D:\privategit\github\stockScience
D:\ProgramData\anaconda3\python.exe strategies/stockPre.py
D:\ProgramData\anaconda3\python.exe strategies/stockRanking.py
```

### 运行测试脚本
```cmd
D:\ProgramData\anaconda3\python.exe tests/verify_diggold.py
D:\ProgramData\anaconda3\python.exe test_env_token.py
```

### 运行掘金排名
```cmd
cd D:\privategit\github\stockScience\stock_grain_ranking
D:\ProgramData\anaconda3\python.exe main.py -s 600489 -b 20250201
```

---

**更新日期**: 2026-02-08
**Python环境**: Anaconda base (D:\ProgramData\anaconda3)
