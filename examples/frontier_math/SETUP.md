# Quick Setup Guide

## 1. Install Dependencies

```bash
pip install python-dotenv
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

## 2. Configure API Key

Create a `.env` file in the `examples/frontier_math/` directory:

```bash
# Copy the example file
cp .env.example .env
```

Then edit `.env` and add your DeepSeek API key:

```
DEEPSEEK_API_KEY=sk-your-actual-key-here
```

**Important**: The `.env` file is gitignored and will not be committed.

## 3. Run the Challenge

```bash
cd examples/frontier_math
python run_artin_challenge.py
```

To capture output to a log file:

```bash
python -u run_artin_challenge.py > artin_challenge.log 2>&1
```

To monitor in real-time (in another terminal):

```bash
Get-Content artin_challenge.log -Wait
```

## Troubleshooting

### API Key Not Found

If you see "DEEPSEEK_API_KEY not found", make sure:
1. The `.env` file exists in `examples/frontier_math/`
2. The file contains `DEEPSEEK_API_KEY=your_key`
3. There are no extra spaces around the `=` sign
4. You're running the script from the correct directory

### Python-dotenv Not Installed

```bash
pip install python-dotenv
```
