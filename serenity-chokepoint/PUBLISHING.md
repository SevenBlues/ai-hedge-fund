# Publishing checklist (team account)

How to release this folder as a standalone public repo `sevenblues/serenity-chokepoint`.
Run these on your own machine (the team account logs in locally fine).

## 1. Get the code
Either download `serenity-chokepoint-v0.1.0.zip` and unzip it, **or** copy the
folder out of the team repo:
```bash
git clone https://github.com/sevenblues/ai-hedge-fund.git
cd ai-hedge-fund && git checkout claude/chokepoint-supply-chain-bJZaM
cp -r serenity-chokepoint ~/serenity-chokepoint
```

## 2. Create the empty public repo
On github.com (team account) → **New repository** → name `serenity-chokepoint`,
**Public**, do NOT add README/.gitignore/license (this folder already has them).

## 3. Initialise and push
```bash
cd ~/serenity-chokepoint
git init
git add .
git commit -m "Initial public release: Serenity Chokepoint Engine v0.1.0"
git branch -M main
git remote add origin https://github.com/sevenblues/serenity-chokepoint.git
git push -u origin main
```
(If the team account uses SSH instead of HTTPS, use
`git@github.com:sevenblues/serenity-chokepoint.git`.)

## 4. Smoke-test before announcing
```bash
pip install -e .
serenity pool          # should print the pool
pytest -q              # 16 tests pass
```

## 5. (Optional) publish to PyPI
```bash
pip install build twine
python -m build
twine upload dist/*    # username __token__, password = PyPI API token
```

## 6. Final polish
- Confirm the URLs in `pyproject.toml` and `README.md` point to
  `sevenblues/serenity-chokepoint` (already set to that).
- Add repo topics on GitHub: `quant`, `investing`, `semiconductors`, `ai`,
  `supply-chain`, `photonics`, `stock-screener`.
- Set the repo description and a social-preview image (use `assets/oos.png`).
