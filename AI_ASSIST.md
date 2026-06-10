# AI Assist Report

> Task 7: Fill in all three sections below with specifics. "The AI fixed it"
> is not enough detail. Show the exact prompt you used, paste the suggestion
> you received, and explain what you changed and why.

## The prompt I gave

<!-- Paste the exact prompt you gave an LLM (ChatGPT, Claude, Copilot, etc.). -->

python pipeline.py
POSTGRES_URL is not set.
Retrieve it from Key Vault using the CLI, then export it before running:

    export POSTGRES_URL="$(az keyvault secret show --vault-name kv-hyf-data --name postgres-url --query value -o tsv)"

Traceback (most recent call last):
  File "C:\Users\Beheerder\c55-data-week-6\src\pipeline.py", line 170, in <module>
    run()
  File "C:\Users\Beheerder\c55-data-week-6\src\pipeline.py", line 152, in run
    config = get_config()
             ^^^^^^^^^^^^
  File "C:\Users\Beheerder\c55-data-week-6\src\pipeline.py", line 53, in get_config
    raise RuntimeError("missing POSTGRES_URL")
RuntimeError: missing POSTGRES_URL
((.venv) ) 
why i got this error i already add the url to .env

## The code or suggestion it returned

<!-- Paste the suggestion verbatim — code, shell commands, or both. -->

```You got this error because even though you saved your URL inside the `.env` file, your terminal hasn't actually read that file into its active memory yet.

Python's `os.environ.get()` function doesn't know how to read a `.env` file automatically—it can only look at variables that are actively loaded into your terminal session's environment memory.

Since you are using **Git Bash**, you need to run the specific commands that read your `.env` file and export those secrets into your terminal's memory.

---

### How to fix it (Load your variables)

Make sure you are in your project folder, your `(.venv)` is active, and run this exact command line in your Git Bash terminal:

```bash
set -a && source .env && set +a

```

### What this just did:

* **`source .env`** told Git Bash to open your `.env` file and read your lines.
* **`set -a`** and **`set +a`** told your terminal to automatically export those lines into its active memory space so that any Python script run afterward can see them.

---

### Test it again!

To make sure your terminal successfully loaded the variables before running your script, you can print them to the screen using `echo`:

```bash
echo $POSTGRES_URL

```

*(If you see your connection string print out in the terminal, it worked perfectly!)*

Now, try running your pipeline module again:

```bash
python -m src.pipeline

```

It should pass right through the `get_config()` check and start executing your cloud pipeline steps!
```

## What I changed after reviewing it

<!-- Describe what you accepted, rejected, or modified, and why. -->

I got another error with the connection string. I discovered that I had entered the URLs for POSTGRES_URL and AZURE_STORAGE_CONNECTION_STRING in my .env file without quotation marks. The AI explained that using double quotation marks ("") is important because it ensures the strings are correctly passed to Python, preventing issues with special characters and protecting critical account details.
