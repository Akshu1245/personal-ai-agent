# AKSHAY AI CORE — Phase 3: Real-World Integration Architecture

## Executive Summary

Phase 3 extends the secure AI platform to the physical world through four bridges:
- **Mobile Bridge** - Android companion app
- **IoT Bridge** - ESP32-based smart home control
- **Cyber Lab Mode** - Security research sandbox
- **Web Automation** - Compliant browser automation

**Core Principle:** The AI NEVER directly touches hardware, network, or OS APIs. All actions flow through trust boundaries with policy enforcement.

---

## 1. TRUST BOUNDARY ARCHITECTURE

### 1.1 Trust Zone Definitions

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TRUST ZONE ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    ZONE 0: AI CORE (HIGHEST TRUST)                   │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │   │
│  │  │   Brain     │  │   Memory    │  │   Policy    │                  │   │
│  │  │  (LLM/RAG)  │  │ Governance  │  │   Engine    │                  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │   │
│  │                           │                                          │   │
│  │              ┌────────────┴────────────┐                            │   │
│  │              │    PERMISSION FIREWALL   │                            │   │
│  │              │    (Phase 2 Security)    │                            │   │
│  │              └────────────┬────────────┘                            │   │
│  └───────────────────────────┼─────────────────────────────────────────┘   │
│                              │                                              │
│  ┌───────────────────────────┼─────────────────────────────────────────┐   │
│  │              ZONE 1: SYSTEM TRUST (CONTROLLED)                       │   │
│  │              ┌────────────┴────────────┐                            │   │
│  │              │     TOOL DISPATCHER      │                            │   │
│  │              └────────────┬────────────┘                            │   │
│  │                           │                                          │   │
│  │  ┌─────────────┐  ┌──────┴──────┐  ┌─────────────┐                  │   │
│  │  │   Audit     │  │  ISOLATION  │  │   Bridge    │                  │   │
│  │  │    Log      │  │   RUNTIME   │  │   Router    │                  │   │
│  │  └─────────────┘  └──────┬──────┘  └─────────────┘                  │   │
│  └───────────────────────────┼─────────────────────────────────────────┘   │
│                              │                                              │
│  ┌───────────────────────────┼─────────────────────────────────────────┐   │
│  │              ZONE 2: USER TRUST (INTERACTIVE)                        │   │
│  │                           │                                          │   │
│  │  ┌─────────────┐  ┌──────┴──────┐  ┌─────────────┐                  │   │
│  │  │  Web UI     │  │   CLI/API   │  │   Mobile    │                  │   │
│  │  │  (Local)    │  │  Interface  │  │   Companion │                  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              ZONE 3: DEVICE TRUST (VERIFIED HARDWARE)                │   │
│  │                                                                      │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │   │
│  │  │  IoT Hub    │  │   Smart     │  │   Sensors   │                  │   │
│  │  │  (ESP32)    │  │   Devices   │  │   (Local)   │                  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              ZONE 4: NETWORK TRUST (UNTRUSTED/ISOLATED)              │   │
│  │                                                                      │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │   │
│  │  │   Cyber     │  │    Web      │  │  External   │                  │   │
│  │  │    Lab      │  │  Automation │  │   APIs      │                  │   │
│  │  │ (Isolated)  │  │ (Allowlist) │  │ (Verified)  │                  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Trust Zone Properties

| Zone | ID | Trust Level | Access Pattern | Verification |
|------|-----|-------------|----------------|--------------|
| **AI Core** | 0 | Highest | Internal only | N/A (trusted) |
| **System** | 1 | High | Authenticated | Session + Role |
| **User** | 2 | Medium | Interactive | Session + MFA |
| **Device** | 3 | Low-Medium | Certified | Device cert + fingerprint |
| **Network** | 4 | Lowest | Isolated | Domain allowlist + TLS |

### 1.3 Trust Boundary Crossing Rules

```
BOUNDARY CROSSING REQUIREMENTS:

Zone 0 → Zone 1:
  - Policy Engine approval
  - Permission Firewall check
  - Audit log entry

Zone 1 → Zone 2:
  - Session validation
  - Rate limiting
  - User confirmation (destructive)

Zone 1 → Zone 3:
  - Device certificate validation
  - Command signing
  - Physical override check

Zone 1 → Zone 4:
  - Domain allowlist check
  - Network isolation verified
  - Legal compliance flag
  - Full packet logging (Cyber Lab)
```

---

## 2. POLICY ENGINE SCHEMA

### 2.1 Policy Rule Format (YAML)

```yaml
# Policy Rule Schema v1.0
apiVersion: policy.akshay.ai/v1
kind: PolicyRule

metadata:
  name: rule-name
  namespace: default
  priority: 100  # Higher = evaluated first
  enabled: true
  
spec:
  # Conditions (ALL must match)
  conditions:
    - field: tool
      operator: equals
      value: web_automation
    - field: domain
      operator: not_in
      value: "@allowlist/web_domains"
    - field: user.role
      operator: in
      value: [admin, power_user]
    - field: time
      operator: between
      value: ["09:00", "18:00"]
    - field: environment
      operator: equals
      value: production
      
  # Action when conditions match
  action: deny  # allow, deny, require_confirmation, rate_limit
  
  # Rate limit config (if action = rate_limit)
  rateLimit:
    requests: 10
    period: 60s
    
  # Confirmation config (if action = require_confirmation)
  confirmation:
    message: "This action will modify external systems. Continue?"
    timeout: 60s
    
  # Audit configuration
  audit:
    level: detailed  # minimal, standard, detailed
    includePayload: false
    
  # Response
  response:
    reason: "External domain blocked by policy"
    code: POLICY_DENIED_DOMAIN
```

### 2.2 Supported Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `equals` | Exact match | `tool equals "web_automation"` |
| `not_equals` | Not equal | `status not_equals "disabled"` |
| `in` | Value in list | `role in [admin, user]` |
| `not_in` | Value not in list | `domain not_in @allowlist` |
| `contains` | String contains | `url contains "api"` |
| `matches` | Regex match | `path matches "^/api/v[0-9]+"` |
| `between` | Range (time, number) | `time between ["09:00", "18:00"]` |
| `greater_than` | Numeric comparison | `risk_score greater_than 7` |
| `less_than` | Numeric comparison | `attempts less_than 3` |

### 2.3 Built-in Policy Variables

```yaml
# Request Context
request.tool           # Tool being invoked
request.action         # Specific action
request.params         # Action parameters
request.timestamp      # Request time (UTC)

# User Context
user.id                # User identifier
user.role              # User role
user.session.id        # Session ID
user.session.elevated  # Has elevated privileges
user.mfa_verified      # MFA status

# Device Context
device.id              # Device fingerprint
device.type            # mobile, iot, browser
device.certified       # Has valid certificate
device.last_seen       # Last activity time

# Environment Context
environment.name       # production, lab, development
environment.network    # home, public, isolated
environment.location   # Optional geo context

# System Context
system.load            # CPU load percentage
system.memory_free     # Available memory
system.time            # Current system time
system.kill_switch     # Kill switch active
```

### 2.4 Allowlist References

```yaml
# Allowlists are referenced with @ prefix
# Stored in /config/allowlists/*.yaml

# Web domains allowlist
# File: /config/allowlists/web_domains.yaml
apiVersion: policy.akshay.ai/v1
kind: Allowlist
metadata:
  name: web_domains
spec:
  type: domain
  entries:
    - "*.github.com"
    - "*.google.com"
    - "api.openai.com"
    - "localhost"
    - "127.0.0.1"

# Device allowlist
# File: /config/allowlists/iot_devices.yaml
apiVersion: policy.akshay.ai/v1
kind: Allowlist
metadata:
  name: iot_devices
spec:
  type: device
  entries:
    - id: "esp32-living-room-001"
      name: "Living Room Light Controller"
      capabilities: [light_control, sensor_read]
    - id: "esp32-bedroom-001"
      name: "Bedroom Fan Controller"
      capabilities: [fan_control, temperature_read]
```

---

## 3. PLUGIN CAPABILITY MANIFEST

### 3.1 Manifest Schema

```yaml
# Plugin Capability Manifest v1.0
apiVersion: plugin.akshay.ai/v1
kind: PluginManifest

metadata:
  name: web-automation-plugin
  version: 1.0.0
  author: system
  description: Browser automation for allowed domains

# Required capabilities (must be granted)
capabilities:
  required:
    - network.outbound        # Can make outbound connections
    - browser.automation      # Can control browser
    - storage.credentials     # Can access credential vault
    
  optional:
    - clipboard.read          # Can read clipboard
    - screenshot.capture      # Can take screenshots

# Resource limits
resources:
  cpu:
    limit: "500m"             # 0.5 CPU cores
    request: "100m"
  memory:
    limit: "512Mi"
    request: "128Mi"
  disk:
    limit: "1Gi"
  network:
    egress_bandwidth: "10Mbps"
    allowed_ports: [80, 443]
    
# Isolation requirements
isolation:
  runtime: container          # process, container, wasm
  network_namespace: isolated # shared, isolated, none
  filesystem: readonly        # readonly, readwrite, none
  allowed_paths:
    - /tmp/plugin-data
    - /config/allowlists
    
# Trust requirements
trust:
  min_zone: 2                 # Minimum trust zone to invoke
  requires_user_present: true
  requires_confirmation: true
  max_execution_time: 300s

# Security constraints
security:
  no_eval: true               # Prevent dynamic code execution
  no_network_scan: true       # Prevent port scanning
  no_system_exec: true        # Prevent subprocess spawning
  audit_all_actions: true
```

### 3.2 Capability Definitions

| Capability | Description | Trust Required |
|------------|-------------|----------------|
| `network.outbound` | Make HTTP(S) requests | Zone 2+ |
| `network.scan` | Network scanning (Cyber Lab only) | Zone 4 + Legal |
| `browser.automation` | Control browser | Zone 2+ |
| `storage.credentials` | Access credential vault | Zone 1 + Elevated |
| `device.control` | Control IoT devices | Zone 3 + Device Cert |
| `device.sensor_read` | Read sensor data | Zone 3 |
| `mobile.notification` | Send push notifications | Zone 2 |
| `mobile.location` | Access location | Zone 2 + User Consent |
| `system.execute` | Run system commands | Zone 1 + Admin |
| `clipboard.read` | Read clipboard | Zone 2 + Confirmation |
| `screenshot.capture` | Take screenshots | Zone 2 + Confirmation |
| `audio.capture` | Record audio | Zone 2 + Explicit Consent |

---

## 4. ISOLATION STRATEGY

### 4.1 Recommended: Hybrid Isolation

```
┌─────────────────────────────────────────────────────────────────┐
│                    ISOLATION STRATEGY                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  TIER 1: PROCESS ISOLATION (Default)                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  - Separate Python processes (multiprocessing)          │   │
│  │  - Resource limits via OS (ulimit, cgroups)             │   │
│  │  - IPC via secure message queue                         │   │
│  │  - Best for: Most plugins, low overhead                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  TIER 2: CONTAINER ISOLATION (High Risk)                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  - Docker containers with strict profiles               │   │
│  │  - Network namespace isolation                          │   │
│  │  - Filesystem mount restrictions                        │   │
│  │  - Best for: Web automation, Cyber Lab                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  TIER 3: WASM SANDBOX (Untrusted Code)                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  - WebAssembly runtime (Wasmtime/Wasmer)                │   │
│  │  - Capability-based security                            │   │
│  │  - Deterministic execution                              │   │
│  │  - Best for: Third-party plugins, sandboxed compute     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Isolation Selection Matrix

| Plugin Type | Risk Level | Isolation | Network | Filesystem |
|-------------|------------|-----------|---------|------------|
| Core plugins | Low | Process | Shared | Restricted |
| Web automation | High | Container | Isolated | None |
| Cyber Lab tools | Critical | Container | Air-gapped | Ephemeral |
| IoT bridge | Medium | Process | Local only | Restricted |
| Mobile bridge | Medium | Process | Encrypted | Restricted |
| Third-party | Unknown | WASM | None | None |

### 4.3 Container Security Profile

```yaml
# Docker security profile for high-risk plugins
# File: /config/isolation/container-profile.yaml

securityContext:
  runAsNonRoot: true
  runAsUser: 65534
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  
capabilities:
  drop:
    - ALL
  add: []
  
seccompProfile:
  type: RuntimeDefault
  
resources:
  limits:
    cpu: "500m"
    memory: "512Mi"
    ephemeral-storage: "1Gi"
  requests:
    cpu: "100m"
    memory: "128Mi"
    
networkPolicy:
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              name: allowed-external
      ports:
        - protocol: TCP
          port: 443
```

---

## 5. DATA FLOW ARCHITECTURE

### 5.1 Request Flow Through Trust Boundaries

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        REQUEST FLOW DIAGRAM                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  USER REQUEST                                                           │
│       │                                                                 │
│       ▼                                                                 │
│  ┌─────────────┐                                                        │
│  │   1. API    │  Validate session, extract context                    │
│  │   Gateway   │                                                        │
│  └──────┬──────┘                                                        │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────┐                                                        │
│  │ 2. Policy   │  Load rules, evaluate conditions                      │
│  │   Engine    │  → DENY early if policy violation                     │
│  └──────┬──────┘                                                        │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────┐                                                        │
│  │3. Permission│  Check RBAC, rate limits, context                     │
│  │  Firewall   │  → DENY if insufficient permissions                   │
│  └──────┬──────┘                                                        │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────┐                                                        │
│  │  4. Tool    │  Route to correct bridge                              │
│  │ Dispatcher  │  Validate manifest, acquire resources                 │
│  └──────┬──────┘                                                        │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────┐                                                        │
│  │5. Isolation │  Start container/process/WASM                         │
│  │  Runtime    │  Apply resource limits                                │
│  └──────┬──────┘                                                        │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────┐                                                        │
│  │  6. Bridge  │  Mobile / IoT / Cyber / Web                           │
│  │  Executor   │  Execute in isolated environment                      │
│  └──────┬──────┘                                                        │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────┐                                                        │
│  │  7. Audit   │  Log full request/response                            │
│  │    Log      │  Hash chain integrity                                 │
│  └──────┬──────┘                                                        │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────┐                                                        │
│  │ 8. Memory   │  Store results in governed memory                     │
│  │ Governance  │  Apply TTL, encryption                                │
│  └──────┬──────┘                                                        │
│         │                                                               │
│         ▼                                                               │
│     RESPONSE                                                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Bridge-Specific Data Flows

#### Mobile Bridge Flow
```
Mobile App → mTLS → API Gateway → Policy Engine → Mobile Bridge
                                                       │
                         ┌─────────────────────────────┤
                         ▼                             ▼
                   Push Service              Voice Processing
                   (FCM/APNS)                    (Local)
```

#### IoT Bridge Flow
```
AI Core → Policy Engine → IoT Bridge → Command Signer
                                            │
                              ┌─────────────┴─────────────┐
                              ▼                           ▼
                       Local WiFi                    Bluetooth
                       (mDNS/CoAP)                   (BLE GATT)
                              │                           │
                              ▼                           ▼
                        ESP32 Hub ◄─────────────► Smart Devices
```

#### Cyber Lab Flow
```
AI Core → Policy Engine → Legal Check → Cyber Lab Bridge
                                              │
                              ┌───────────────┴───────────────┐
                              ▼                               ▼
                     ┌─────────────┐                  ┌─────────────┐
                     │  ISOLATED   │                  │   PACKET    │
                     │  CONTAINER  │                  │   CAPTURE   │
                     └─────────────┘                  └─────────────┘
                              │                               │
                              └───────────────┬───────────────┘
                                              ▼
                                      ┌─────────────┐
                                      │  ISOLATED   │
                                      │   NETWORK   │
                                      │ (Air-gapped)│
                                      └─────────────┘
```

#### Web Automation Flow
```
AI Core → Policy Engine → Domain Check → Web Bridge
                                              │
                              ┌───────────────┴───────────────┐
                              ▼                               ▼
                     ┌─────────────┐                  ┌─────────────┐
                     │ CREDENTIAL  │                  │  BROWSER    │
                     │   VAULT     │                  │  CONTAINER  │
                     └─────────────┘                  └─────────────┘
                                                              │
                                                              ▼
                                                     ┌─────────────┐
                                                     │   ALLOWED   │
                                                     │   DOMAINS   │
                                                     │    ONLY     │
                                                     └─────────────┘
```

---

## 6. SECURITY CONTROLS BY BRIDGE

### 6.1 Mobile Bridge Security

| Control | Implementation |
|---------|----------------|
| **Transport** | Mutual TLS with certificate pinning |
| **Authentication** | Device fingerprint + user session |
| **Session Binding** | Tied to device ID + IP (optional) |
| **Emergency Lock** | Remote wipe via push + local kill |
| **Offline Mode** | Cached policies, no network actions |
| **Data at Rest** | Android Keystore encryption |

### 6.2 IoT Bridge Security

| Control | Implementation |
|---------|----------------|
| **Device Auth** | X.509 certificates per device |
| **Command Signing** | HMAC-SHA256 with device key |
| **Allowlist** | Only registered devices accepted |
| **Network Seg** | Separate VLAN/subnet for IoT |
| **Physical Override** | Hardware button disables AI control |
| **Local First** | No cloud dependency required |

### 6.3 Cyber Lab Security

| Control | Implementation |
|---------|----------------|
| **Legal Toggle** | Explicit user acknowledgment required |
| **Network Isolation** | Air-gapped container network |
| **Target Restriction** | Only scan owned/authorized systems |
| **Full Logging** | Every packet captured and logged |
| **Time Limits** | Auto-shutdown after timeout |
| **Approval Per Run** | Each scan requires fresh approval |

### 6.4 Web Automation Security

| Control | Implementation |
|---------|----------------|
| **Domain Allowlist** | Explicit list of allowed domains |
| **Credential Vault** | Encrypted storage, never in logs |
| **Rate Throttling** | Max requests per domain per minute |
| **CAPTCHA Detection** | Pause and alert on CAPTCHA |
| **Compliance Flags** | GDPR, CCPA tracking |
| **Session Isolation** | Each automation in fresh browser |

---

## 7. DECISION: ISOLATION RUNTIME

### Recommended Approach: **Hybrid Process + Container**

**Rationale:**
1. **Process Isolation** (Default) - Low overhead for most operations
2. **Container Isolation** (High Risk) - Full isolation for web/cyber
3. **WASM** (Future) - Optional for third-party plugins

**Why not pure WASM:**
- Python ecosystem not fully WASM-compatible
- Existing plugins need rewrite
- Network capabilities limited in WASM

**Why not pure Container:**
- Overhead too high for simple operations
- Docker dependency on all platforms
- Cold start latency

**Implementation:**
```python
class IsolationRuntime:
    def select_isolation(self, manifest: PluginManifest) -> IsolationType:
        if manifest.trust.min_zone >= 4:  # Network zone
            return IsolationType.CONTAINER
        if "network.scan" in manifest.capabilities.required:
            return IsolationType.CONTAINER
        if manifest.isolation.runtime == "wasm":
            return IsolationType.WASM
        return IsolationType.PROCESS
```

---

## 8. APPROVAL CHECKPOINT

### Questions for Review

1. **Trust Zone Model**
   - Are the 5 zones sufficient?
   - Should devices and network be separate zones?

2. **Policy Engine**
   - Is YAML the right format vs JSON?
   - Should policies support inheritance?

3. **Capability Manifest**
   - Are the capability categories complete?
   - Should we add more granular permissions?

4. **Isolation Strategy**
   - Is hybrid process+container acceptable?
   - Should WASM be implemented in Phase 3 or deferred?

5. **Bridge Priorities**
   - Which bridge should be implemented first?
   - Any bridges that can be deferred?

### Sign-off Required

- [ ] Trust Boundary Architecture approved
- [ ] Policy Engine schema approved
- [ ] Capability manifest design approved
- [ ] Isolation strategy approved

---

## NEXT STEPS (After Approval)

1. **Policy Engine Implementation** (~800 lines)
   - Rule parser and evaluator
   - Allowlist management
   - Policy hot-reload

2. **Isolation Runtime** (~600 lines)
   - Process isolation manager
   - Container orchestrator
   - Resource limiter

3. **Bridge Implementations**
   - Mobile Bridge (~1000 lines)
   - IoT Bridge (~800 lines)
   - Cyber Lab (~700 lines)
   - Web Automation (~900 lines)

4. **Integration Tests** (~500 lines)
   - Trust boundary crossing tests
   - Policy enforcement tests
   - Isolation escape tests

---

*Document Version: 1.0*
*Author: Security Architecture Team*
*Status: PENDING APPROVAL*
