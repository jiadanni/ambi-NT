# Tailscale Integration Guide

Tailscale provides secure, zero-config networking for your Ambient Intelligence nodes. This is the recommended approach for Phase 1 deployment with friends, as it eliminates the need for port forwarding and provides automatic encryption.

## Why Tailscale?

- **Zero Configuration**: No port forwarding or firewall rules needed
- **Automatic Encryption**: All traffic encrypted by WireGuard
- **NAT Traversal**: Works behind NAT/firewalls automatically
- **Peer-to-Peer**: Direct connections when possible
- **Easy Sharing**: Simple URL sharing with friends
- **Free Tier**: Up to 100 devices on personal plan

## Installation

### Linux
```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

### macOS
```bash
brew install tailscale
```

Or download from: https://tailscale.com/download/mac

### Windows
Download installer from: https://tailscale.com/download/windows

## Setup for Node Operators

### 1. Install Tailscale

Follow the installation instructions above for your platform.

### 2. Authenticate

```bash
sudo tailscale up
```

This will open a browser window to authenticate with your Tailscale account (or create one).

### 3. Get Your Tailscale IP

```bash
tailscale ip -4
```

Example output: `100.64.1.5`

### 4. Start Your Ambient Intelligence Node

```bash
# Using Docker
./scripts/docker-setup.sh

# Or manually
cd node
python server.py
```

### 5. Share Your Node URL

Share this with friends:
```
http://<your-tailscale-ip>:8000
```

For example:
```
http://100.64.1.5:8000
```

### 6. Test Accessibility

On another device in your Tailscale network:
```bash
curl http://100.64.1.5:8000/health
```

Should return:
```json
{
  "status": "healthy",
  "ollama_available": true,
  "active_jobs": 0
}
```

## Setup for Clients

### 1. Install Tailscale

Same as above - install on your client device.

### 2. Join the Same Network

```bash
sudo tailscale up
```

Authenticate with the same Tailscale account as the node operator, or have them share their network.

### 3. Access Nodes

You can now access any node on your Tailscale network:

**Web Client:**
1. Open http://localhost:8080 (if running web client locally)
2. Or open your node's web client at http://<tailscale-ip>:8080
3. Enter node URL: `http://<node-tailscale-ip>:8000`
4. Submit your query!

**CLI Client:**
```bash
python client-cli/client.py --node http://100.64.1.5:8000 "What is 2+2?"
```

## Sharing with Friends (Phase 1)

### Option 1: Share Access to Your Tailnet

Invite friends to your Tailscale network:

1. Go to https://login.tailscale.com/admin/machines
2. Click "Share" next to your machine
3. Send the sharing link to your friend
4. They can now access your node!

### Option 2: Use Tailscale Funnels (Public Access)

For Phase 2+, you can expose your node publicly while still using Tailscale:

```bash
tailscale funnel 8000
```

This creates a public HTTPS URL like:
```
https://your-machine.your-tailnet.ts.net
```

**Warning**: Only use funnels if you understand the security implications. Your node will be publicly accessible.

## Best Practices

### Security

1. **Keep Tailscale Updated**
   ```bash
   sudo tailscale update
   ```

2. **Use ACLs (Access Control Lists)**

   In Tailscale admin console, restrict access:
   ```json
   {
     "acls": [
       {
         "action": "accept",
         "src": ["group:friends"],
         "dst": ["tag:ambient-node:8000"]
       }
     ]
   }
   ```

3. **Monitor Access**

   Check connected devices:
   ```bash
   tailscale status
   ```

4. **Disable Key Expiry** (for always-on nodes)

   In Tailscale admin console:
   - Go to Machines
   - Click your node
   - Disable key expiry

### Performance

1. **Enable Direct Connections**

   Tailscale will use peer-to-peer when possible, falling back to relay servers (DERP) when necessary.

   Check connection type:
   ```bash
   tailscale status
   ```

   Look for "direct" vs "relay" in the output.

2. **Optimize for Low Latency**

   Tailscale automatically chooses the best path. For AI inference, direct connections provide the best latency.

### Monitoring

1. **Check Tailscale Status**
   ```bash
   tailscale status
   ```

2. **View Logs**
   ```bash
   sudo journalctl -u tailscaled -f
   ```

3. **Test Connectivity**
   ```bash
   tailscale ping <peer-name>
   ```

## Troubleshooting

### Node Not Accessible

1. **Check Tailscale is Running**
   ```bash
   tailscale status
   ```

2. **Verify IP Address**
   ```bash
   tailscale ip -4
   ```

3. **Test Local Access**
   ```bash
   curl http://localhost:8000/health
   ```

4. **Check Firewall**

   Tailscale usually handles this, but verify:
   ```bash
   # Linux
   sudo ufw status

   # macOS
   /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate
   ```

### Slow Connections

1. **Check if Using Relay**
   ```bash
   tailscale status
   ```

   If showing "relay", try:
   - Ensure UDP is not blocked
   - Check NAT type
   - Try disabling IPv6 if issues persist

2. **Test Bandwidth**
   ```bash
   tailscale ping <peer> --until-direct
   ```

### Authentication Issues

1. **Re-authenticate**
   ```bash
   tailscale logout
   tailscale up
   ```

2. **Check Account Limits**

   Free tier: 100 devices
   If exceeded, remove unused devices in admin console.

## Advanced: MagicDNS

Enable MagicDNS for easier access (no need to remember IPs):

1. Go to https://login.tailscale.com/admin/dns
2. Enable MagicDNS
3. Access nodes by name:
   ```
   http://node-name:8000
   ```

## Integration with Docker

### Option 1: Host Networking

```yaml
# docker-compose.yml
services:
  node:
    network_mode: host
    # ... rest of config
```

This allows the container to use host's Tailscale connection.

### Option 2: Tailscale in Container

```yaml
# docker-compose.yml
services:
  node:
    image: tailscale/tailscale:latest
    # ... configure Tailscale in container
```

**Recommended**: Use Option 1 (host networking) for simplicity in Phase 1.

## Cost

- **Personal Use**: Free (up to 100 devices, 3 users)
- **Teams**: $5/user/month
- **Business**: $15/user/month

For Phase 1 with friends, the free tier is sufficient.

## Alternatives to Tailscale

If you prefer not to use Tailscale:

1. **ZeroTier**: Similar to Tailscale, also free tier
2. **Cloudflare Tunnel**: Free, but more complex setup
3. **Traditional VPN**: OpenVPN, WireGuard
4. **Port Forwarding**: Not recommended (security risks)

## Resources

- Tailscale Docs: https://tailscale.com/kb/
- Tailscale Admin Console: https://login.tailscale.com/admin
- Status Page: https://status.tailscale.com/

## Next Steps

Once you have Tailscale set up:

1. **Phase 1**: Share your node with 10-20 friends
2. **Phase 2**: Deploy coordinator on a VPS (also via Tailscale)
3. **Phase 3**: Federation between multiple networks

---

**Questions?** Open an issue on GitHub or check the main documentation.
