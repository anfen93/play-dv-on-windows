# Contributing

Thanks for your interest in contributing to this project. Here's what you need to know:

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Set up development environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -e .
   pip install -r requirements-test.txt
   ```
4. Install pre-commit hooks: `pre-commit install`
5. Run tests to ensure everything works: `python run_tests.py all`

## Making Changes

1. Create a branch for your changes
2. Make your modifications
3. Add tests for new functionality
4. Ensure all tests pass: `python3 run_tests.py all`
5. Update documentation if needed

## Submitting Changes

1. Push your changes to your fork
2. Open a pull request with a clear description of what you've changed
3. Wait for review

## Code Guidelines

- Code is automatically formatted with Black
- Add tests for new features
- Update documentation for user-facing changes
- Keep commits focused and add clear commit messages

## Testing

Run tests before submitting:
```bash
# All tests
python3 run_tests.py all

# Specific modules
python3 run_tests.py convert
python3 run_tests.py qbt

# With coverage
python3 run_tests.py coverage
```

## Reporting Issues

- Use the issue tracker for bugs and feature requests
- Include system information (OS, Python version, FFmpeg version)
- Provide clear reproduction steps for bugs
- Check if the issue already exists

## Working with Claude Code

This project is optimized for AI-assisted development with [Claude Code](https://claude.ai/code). We've included comprehensive documentation and tooling to make AI collaboration effective.

### Using Claude Code
1. **Start with CLAUDE.md**: The project includes `CLAUDE.md` with detailed context about architecture, commands, and workflows
2. **VSCode Setup**: Use the included `.vscode/` settings for optimal development experience
3. **Project Context**: Claude Code can read the entire codebase and understand the project structure automatically

### AI Development Best Practices
- **Reference CLAUDE.md**: Point Claude Code to `CLAUDE.md` for project-specific guidance
- **Use Pre-commit Hooks**: Claude Code can run `pre-commit run --all-files` to ensure code quality
- **Test-Driven Development**: Ask Claude Code to run `python run_tests.py all` before and after changes
- **Follow Existing Patterns**: The AI can analyze existing code patterns and maintain consistency

### Maintaining AI Documentation
When making significant changes:
- Update `CLAUDE.md` if you change development workflows
- Keep the VSCode settings current with project needs
- Ensure new features are documented for future AI assistance

### Example Claude Code Session
```
# Tell Claude Code about the project
"Read CLAUDE.md to understand this project, then help me add a new feature for..."

# Use the development commands
"Run the tests and fix any issues you find"
"Format the code using our pre-commit hooks"
```

## Questions

- Check the documentation in the `docs/` directory first
- Review `CLAUDE.md` for AI-specific project guidance
- Look at existing issues and discussions
- Open an issue for questions that might help others

That's it. Keep it simple and focused on making the tool better.
