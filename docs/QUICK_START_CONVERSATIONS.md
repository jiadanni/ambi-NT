# Quick Start: Conversation Mode

## TL;DR

```bash
# Start the node
cd node
python server.py

# In another terminal - start conversation mode
cd client-cli
python conversation_client.py

# Chat away!
> What is machine learning?
> Can you give me an example?
> Explain that code in detail
```

## Requirements

```bash
pip install pydantic requests PyNaCl
```

## How It Works

1. **You type a message** → Encrypted and sent with full conversation history
2. **Node processes it** → Sees the context, generates response, forgets everything
3. **Response comes back** → Added to your local history
4. **Repeat** → Each request includes all previous context

## Interactive Commands

| Command | What It Does |
|---------|--------------|
| `/exit` | Quit conversation mode |
| `/clear` | Start fresh (clear history) |
| `/save` | Save conversation to disk |
| `/load` | Load a previous conversation |
| `/list` | Show all saved conversations |

## Example Session

```
$ python conversation_client.py

Ambient Intelligence - Conversation Mode
============================================================
Node: http://localhost:8000
Context window: 4096 tokens
============================================================

Commands:
  /clear    - Clear conversation history
  /save     - Save conversation to disk
  /load     - Load a previous conversation
  /list     - List saved conversations
  /exit     - Exit conversation mode
============================================================

⚠️  WARNING: Conversations are stored UNENCRYPTED locally!
   Anyone with access to your computer can read them.
   Recommended: Use full-disk encryption.

> What is Python?

[Encrypting and sending...]

────────────────────────────────────────────────────────────
Python is a high-level, interpreted programming language...
────────────────────────────────────────────────────────────

> Show me a simple example

[Encrypting and sending...]

────────────────────────────────────────────────────────────
Here's a simple Python example:

```python
def greet(name):
    return f"Hello, {name}!"

print(greet("World"))
```
────────────────────────────────────────────────────────────

> Can you explain what f-strings are?

[Encrypting and sending...]

────────────────────────────────────────────────────────────
In the previous example, I used an f-string (the `f"Hello..."` part).
F-strings are a way to embed expressions inside string literals...
────────────────────────────────────────────────────────────

> /save
Conversation saved: 1736985234
Location: /Users/you/.ambient-conversations/1736985234.json

> /exit
Goodbye!
```

## Privacy Notice

### 🔒 In Transit
- All messages encrypted with NaCl (Curve25519)
- Node never sees your public key history
- Forward secrecy per session

### ⚠️ On Disk
- Conversations stored as **PLAINTEXT JSON**
- Location: `~/.ambient-conversations/`
- Anyone with filesystem access can read them

### 🛡️ Recommendations
1. Use full-disk encryption (FileVault, BitLocker, LUKS)
2. Don't share sensitive information
3. Delete old conversations: `rm ~/.ambient-conversations/*`
4. Or use `/clear` command frequently

### 🔮 Future
Password-protected conversation encryption is planned but not yet implemented.

## Programmatic Usage

```python
from conversation_client import ConversationClient

# Create client
client = ConversationClient("http://localhost:8000")

# Have a conversation
client.add_user_message("What is Python?")
response1 = client.submit_conversation()
print(response1)

client.add_assistant_message(response1)
client.add_user_message("Show me an example")
response2 = client.submit_conversation()
print(response2)

# Clear and start over
client.clear_history()
```

## Advanced Configuration

### Custom Storage Directory

```bash
python conversation_client.py --storage-dir /path/to/conversations
```

### Custom Node URL

```bash
python conversation_client.py --node http://192.168.1.100:8000
```

### Environment Variable

```bash
export DEFAULT_NODE_URL=http://192.168.1.100:8000
python conversation_client.py
```

## Context Window

- **Default**: 4096 tokens (~3000 words)
- **Automatic**: Old messages automatically truncated
- **Smart**: System prompts always preserved
- **Transparent**: You'll see truncation in node logs

### What Gets Kept

1. System messages (if any) - always preserved
2. Recent conversation turns
3. Working backwards until token limit reached

### Manual Control

```python
client.max_context_tokens = 2048  # Smaller window
```

## Troubleshooting

### "Connection refused"

```bash
# Make sure the node is running!
cd node
python server.py
```

### "Job failed - Invalid conversation format"

This usually means:
- First message wasn't from user
- Empty message in conversation
- Corrupted saved conversation

Solution: `/clear` and start fresh

### "Rate limit exceeded"

You're sending too many requests. Wait 60 seconds or adjust rate limits in node config.

### Slow Responses

Normal! LLM inference takes time:
- Small model (7B): 10-30 seconds
- Large model (70B): 60-120 seconds
- Depends on hardware (CPU vs GPU)

## Comparison to Single-Prompt Mode

### Single Prompt (Original)

```bash
python client.py "What is 2+2?"
# Answer: 4

python client.py "What did I just ask you?"
# Answer: (No context - doesn't know)
```

### Conversation Mode (New)

```bash
python conversation_client.py
> What is 2+2?
# Answer: 4
> What did I just ask you?
# Answer: You asked me "What is 2+2?"
```

## Best Practices

1. **Use `/clear` often** - Start fresh conversations for new topics
2. **Save important conversations** - Use `/save` before `/exit`
3. **Review saved conversations** - Clean up with `/list` and manual deletion
4. **Enable disk encryption** - Protect your conversation history
5. **Don't overshare** - Remember conversations are stored locally

## Technical Details

Want to understand how it works under the hood?

See [CONVERSATION_SUPPORT.md](CONVERSATION_SUPPORT.md) for:
- Architecture diagrams
- Implementation details
- Security model
- Token estimation logic
- Testing strategy

## Feedback & Issues

Found a bug? Have a suggestion?

https://github.com/anthropics/claude-code/issues

---

**Ready to chat?**

```bash
python conversation_client.py
```
