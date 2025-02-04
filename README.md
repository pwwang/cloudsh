# cloudsh

A Python CLI that wraps common Linux commands for both local and cloud files using [cloudpathlib](https://github.com/drivendataorg/cloudpathlib).

## Installation

```bash
pip install -U cloudsh

# Install for different cloud storage providers
pip install -U cloudsh[gcs]  # Google Cloud Storage
pip install -U cloudsh[aws]  # Amazon S3
pip install -U cloudsh[azure]  # Azure Blob Storage

# Install for all cloud storage providers
pip install -U cloudsh[all]
```

## Usage

`cloudsh` provides common Linux commands that work with both local and cloud files. Currently supported commands include:

- `cat`: Concatenate and print files
- `cp`: Copy files and directories
- `head`: Output the first part of files
- `ls`: List directory contents
- `mkdir`: Make directories
- `mv`: Move files and directories
- `rm`: Remove files and directories
- `tail`: Output the last part of files
- `touch`: Create empty files

And two additional commands:

- `complete`: Generate shell completion scripts
- `sink`: Redirect output to a file

### Authentication

See: https://cloudpathlib.drivendata.org/stable/authentication/ for details on how to authenticate with cloud storage providers.

### The commands works on local files as the GNU/Linux commands do

```bash
$ cloudsh ls /tmp
$ cloudsh cp /tmp/file.txt /tmp/file2.txt
```

### The commands works on cloud files

```bash
$ cloudsh ls gs://my-bucket
$ cloudsh touch gs://my-bucket/file.txt
```

### The commands works between local and cloud files

```bash
$ cloudsh cp /tmp/file.txt gs://my-bucket/file.txt
$ cloudsh mv gs://my-bucket/file.txt /tmp/file.txt
```

### The `sink` command redirects output to a file

```bash
# It is easy to redirect output to a local file
$ echo "Hello, World!" > /tmp/hello.txt
# But it is not so easy to redirect output to a cloud file, so we use `sink`
$ echo "Hello, World!" | cloudsh sink gs://my-bucket/hello.txt
# Append to a cloud file
$ echo "Hello, World!" | cloudsh sink -a gs://my-bucket/hello.txt
```

## Best Practices

Since the commands work on local files as well, you can make aliases to use `cloudsh` as a drop-in replacement for the GNU/Linux commands.

```bash
alias cat='cloudsh cat'
alias cp='cloudsh cp'
alias head='cloudsh head'
alias ls='cloudsh ls'
alias mkdir='cloudsh mkdir'
alias mv='cloudsh mv'
alias rm='cloudsh rm'
alias tail='cloudsh tail'
alias touch='cloudsh touch'
```

What if I want to use the original GNU/Linux commands?

```bash
# alias ls='cloudsh ls'
ls -- -l  # actually executes `/usr/bin/ls -l`
```

## Shell Completion

### Generating Shell Completion Scripts

`cloudsh` provides shell completion, including the subcommands, options and both local and cloud paths, support for bash, zsh and fish. To enable it:

```bash
# For bash
mkdir -p ~/.local/share/bash-completion
cloudsh complete --shell bash > ~/.local/share/bash-completion/cloudsh
activate-global-python-argcomplete --user
# Restart your shell
```

```bash
# For zsh
# Create the completions directory
mkdir -p ~/.zsh/completions

# Generate the Zsh script
cloudsh complete --shell zsh > ~/.zsh/completions/_cloudsh

# Update ~/.zshrc
echo 'fpath=(~/.zsh/completions $fpath)' >> ~/.zshrc
echo 'autoload -Uz compinit && compinit' >> ~/.zshrc

# Restart your shell
```

```bash
# For fish
cloudsh complete --shell fish > ~/.config/fish/completions/cloudsh.fish
```

### Using a caching file for the completion to avoid latency when completing cloud paths

```bash
# Only cache the paths at depth 2 in the bucket
cloudsh complete --update-cache --depth 2 gs://my-bucket
```

> [!NOTE]
> Remember to update the cache when the bucket structure changes.
> You can set up a cron job to update the cache periodically.
