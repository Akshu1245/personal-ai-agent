# AKSHAY AI CORE — Phase 3 Threat Model

## STRIDE + MITRE ATT&CK Analysis

---

## 1. STRIDE THREAT ANALYSIS

### 1.1 Spoofing Identity

| Threat | Component | Attack Vector | Mitigation |
|--------|-----------|---------------|------------|
| **S1** | Mobile Bridge | Attacker clones app, spoofs device ID | Device fingerprint + certificate pinning |
| **S2** | IoT Bridge | Fake ESP32 joins network | X.509 device certificates, allowlist |
| **S3** | API Gateway | Session token theft | Short-lived tokens, IP binding, MFA |
| **S4** | Web Automation | Credential vault impersonation | Vault only accessible via elevated session |
| **S5** | Cyber Lab | Attacker poses as legal user | Legal acknowledgment + admin approval per scan |

### 1.2 Tampering

| Threat | Component | Attack Vector | Mitigation |
|--------|-----------|---------------|------------|
| **T1** | Policy Engine | Modify policy files on disk | File integrity monitoring, signed policies |
| **T2** | IoT Commands | MITM alters commands in transit | HMAC-SHA256 command signing |
| **T3** | Audit Log | Attacker modifies audit entries | Hash chain, append-only storage |
| **T4** | Plugin Manifest | Escalate capabilities post-install | Manifest hash verification at runtime |
| **T5** | Mobile App | APK tampering | Code signing, Play Integrity API |

### 1.3 Repudiation

| Threat | Component | Attack Vector | Mitigation |
|--------|-----------|---------------|------------|
| **R1** | All Bridges | User denies performing action | Immutable audit log with user signature |
| **R2** | Cyber Lab | User claims didn't authorize scan | Explicit consent recording with timestamp |
| **R3** | IoT Bridge | Device claims didn't receive command | Command acknowledgment logging |
| **R4** | Web Automation | Deny accessing specific domain | Full URL logging (excluding credentials) |

### 1.4 Information Disclosure

| Threat | Component | Attack Vector | Mitigation |
|--------|-----------|---------------|------------|
| **I1** | Credential Vault | Memory dump exposes secrets | Encrypted memory, secure wipe |
| **I2** | Mobile Bridge | App data extracted from device | Android Keystore, no plaintext storage |
| **I3** | Audit Log | Sensitive data in logs | PII redaction, credential masking |
| **I4** | Container | Container escape, read host files | seccomp, no privileged mode, read-only fs |
| **I5** | Network Traffic | TLS downgrade, packet sniffing | TLS 1.3 only, certificate pinning |

### 1.5 Denial of Service

| Threat | Component | Attack Vector | Mitigation |
|--------|-----------|---------------|------------|
| **D1** | Policy Engine | Regex ReDoS in rule evaluation | Regex timeout, complexity limits |
| **D2** | Isolation Runtime | Fork bomb in container | cgroups limits, PID limits |
| **D3** | IoT Bridge | Flood device with commands | Rate limiting per device |
| **D4** | Web Automation | Infinite page loads | Timeout per operation, circuit breaker |
| **D5** | Audit Log | Fill disk with log spam | Log rotation, rate limiting |

### 1.6 Elevation of Privilege

| Threat | Component | Attack Vector | Mitigation |
|--------|-----------|---------------|------------|
| **E1** | Plugin Sandbox | Container escape to host | No privileged mode, seccomp, no capabilities |
| **E2** | Policy Engine | Bypass policy with crafted input | Input validation, no dynamic eval |
| **E3** | IoT Bridge | Escalate from sensor to actuator | Capability-based access per device |
| **E4** | Mobile Bridge | Local app escalates to system | Minimal Android permissions |
| **E5** | Web Automation | XSS in automation target | Content Security Policy, sandboxed browser |

---

## 2. MITRE ATT&CK MAPPING

### 2.1 Initial Access (TA0001)

| Technique | ID | Applicability | Mitigation |
|-----------|-----|---------------|------------|
| Phishing | T1566 | User tricked into authorizing malicious action | Confirmation prompts, action previews |
| Supply Chain | T1195 | Malicious plugin package | Plugin signing, manifest verification |
| Trusted Relationship | T1199 | Compromised mobile app used | Device attestation, certificate pinning |
| External Remote Services | T1133 | API exposed to internet | Firewall rules, VPN for remote access |

### 2.2 Execution (TA0002)

| Technique | ID | Applicability | Mitigation |
|-----------|-----|---------------|------------|
| Command & Scripting | T1059 | Plugin executes system commands | `no_system_exec` capability flag |
| Container Admin | T1609 | Escape container to run on host | Minimal container, no Docker socket |
| Native API | T1106 | Direct syscalls from plugin | seccomp profile blocks dangerous calls |
| Scheduled Task | T1053 | Automation runs malicious task | Automation safety layer approval |

### 2.3 Persistence (TA0003)

| Technique | ID | Applicability | Mitigation |
|-----------|-----|---------------|------------|
| Account Creation | T1136 | Create backdoor user | Admin-only user creation, audit all |
| Boot Autostart | T1547 | Malicious plugin auto-starts | Plugin allowlist, signed manifests |
| Scheduled Task | T1053 | Persistent automation rule | Rule requires admin approval |

### 2.4 Privilege Escalation (TA0004)

| Technique | ID | Applicability | Mitigation |
|-----------|-----|---------------|------------|
| Container Escape | T1611 | Break out of isolation | No privileged mode, user namespaces |
| Exploitation | T1068 | Exploit vulnerability in runtime | Regular updates, dependency scanning |
| Valid Accounts | T1078 | Steal elevated session | Session binding, MFA, short TTL |

### 2.5 Defense Evasion (TA0005)

| Technique | ID | Applicability | Mitigation |
|-----------|-----|---------------|------------|
| Disable Logging | T1562 | Stop audit log | Audit log is append-only, monitored |
| Masquerading | T1036 | Plugin pretends to be trusted | Plugin ID verification, hash check |
| Modify Policy | T1562 | Change firewall rules | Policy files are signed, monitored |

### 2.6 Credential Access (TA0006)

| Technique | ID | Applicability | Mitigation |
|-----------|-----|---------------|------------|
| Credential Dumping | T1003 | Extract vault contents | Vault encryption, no plaintext |
| Input Capture | T1056 | Keylogger in web automation | Isolated browser, no keylog capability |
| Steal Session | T1539 | Copy session cookie | IP binding, device binding |

### 2.7 Discovery (TA0007)

| Technique | ID | Applicability | Mitigation |
|-----------|-----|---------------|------------|
| Network Scanning | T1046 | Cyber Lab scans external | Legal mode toggle, isolated network |
| System Info | T1082 | Plugin reads system details | Minimal capabilities, sandboxing |
| Account Discovery | T1087 | Enumerate users | User list not exposed to plugins |

### 2.8 Lateral Movement (TA0008)

| Technique | ID | Applicability | Mitigation |
|-----------|-----|---------------|------------|
| Internal Spearphishing | T1534 | Use AI to social engineer | AI output review, no auto-send |
| Remote Services | T1021 | Pivot through IoT to LAN | IoT on isolated VLAN |

### 2.9 Collection (TA0009)

| Technique | ID | Applicability | Mitigation |
|-----------|-----|---------------|------------|
| Clipboard Data | T1115 | Web automation reads clipboard | `clipboard.read` requires confirmation |
| Screen Capture | T1113 | Screenshot sensitive data | `screenshot.capture` requires confirmation |
| Audio Capture | T1123 | Record conversations | `audio.capture` explicit consent required |

### 2.10 Exfiltration (TA0010)

| Technique | ID | Applicability | Mitigation |
|-----------|-----|---------------|------------|
| Over C2 Channel | T1041 | Plugin sends data to attacker | Egress allowlist, traffic monitoring |
| Over Alternative Protocol | T1048 | DNS exfiltration | DNS logging, no raw socket access |

### 2.11 Impact (TA0040)

| Technique | ID | Applicability | Mitigation |
|-----------|-----|---------------|------------|
| Data Destruction | T1485 | Delete user data | Backup system, confirmation for delete |
| Service Stop | T1489 | Kill switch abuse | Kill switch requires admin + reason |
| Resource Hijacking | T1496 | Crypto mining in container | CPU limits, monitoring |

---

## 3. BRIDGE-SPECIFIC THREATS

### 3.1 Mobile Bridge Threat Matrix

```
┌─────────────────────────────────────────────────────────────────┐
│                  MOBILE BRIDGE THREATS                          │
├──────────────────┬──────────────────┬───────────────────────────┤
│ Attack Surface   │ Threat           │ Mitigation                │
├──────────────────┼──────────────────┼───────────────────────────┤
│ APK              │ Reverse engineer │ ProGuard, native libs     │
│ Network          │ MITM             │ Certificate pinning       │
│ Storage          │ Data extraction  │ Android Keystore          │
│ IPC              │ Intent hijacking │ Explicit intents only     │
│ Push             │ Fake push msgs   │ Server-side validation    │
│ Biometric        │ Bypass auth      │ Android BiometricPrompt   │
└──────────────────┴──────────────────┴───────────────────────────┘
```

### 3.2 IoT Bridge Threat Matrix

```
┌─────────────────────────────────────────────────────────────────┐
│                    IoT BRIDGE THREATS                           │
├──────────────────┬──────────────────┬───────────────────────────┤
│ Attack Surface   │ Threat           │ Mitigation                │
├──────────────────┼──────────────────┼───────────────────────────┤
│ Firmware         │ Backdoor install │ Signed firmware updates   │
│ WiFi             │ Rogue AP         │ Certificate validation    │
│ Bluetooth        │ BlueBorne        │ BLE with pairing required │
│ Physical         │ Hardware tamper  │ Tamper-evident enclosure  │
│ Commands         │ Replay attack    │ Nonce + timestamp in sig  │
│ Sensors          │ Spoofed readings │ Anomaly detection         │
└──────────────────┴──────────────────┴───────────────────────────┘
```

### 3.3 Cyber Lab Threat Matrix

```
┌─────────────────────────────────────────────────────────────────┐
│                   CYBER LAB THREATS                             │
├──────────────────┬──────────────────┬───────────────────────────┤
│ Attack Surface   │ Threat           │ Mitigation                │
├──────────────────┼──────────────────┼───────────────────────────┤
│ Network          │ Scan external    │ Air-gapped container net  │
│ Tools            │ Malicious tool   │ Curated tool list only    │
│ Results          │ Data exfil       │ No egress, manual export  │
│ Legal            │ Unauthorized use │ Legal consent per session │
│ Container        │ Escape           │ gVisor/Kata containers    │
│ Malware          │ Infection spread │ Ephemeral containers      │
└──────────────────┴──────────────────┴───────────────────────────┘
```

### 3.4 Web Automation Threat Matrix

```
┌─────────────────────────────────────────────────────────────────┐
│                 WEB AUTOMATION THREATS                          │
├──────────────────┬──────────────────┬───────────────────────────┤
│ Attack Surface   │ Threat           │ Mitigation                │
├──────────────────┼──────────────────┼───────────────────────────┤
│ Browser          │ XSS injection    │ Sandboxed browser profile │
│ Credentials      │ Vault breach     │ Encrypted, never logged   │
│ Target site      │ Unauthorized use │ Domain allowlist          │
│ Data             │ PII exposure     │ Compliance flags, masking │
│ Rate             │ Site blocking    │ Rate limiting, delays     │
│ Session          │ Cookie theft     │ Isolated browser per task │
└──────────────────┴──────────────────┴───────────────────────────┘
```

---

## 4. SECURITY CONTROL MATRIX

### 4.1 Control Implementation Status

| Control | Mobile | IoT | Cyber Lab | Web Auto |
|---------|--------|-----|-----------|----------|
| mTLS | Required | N/A | N/A | N/A |
| Device Cert | ✓ | ✓ | N/A | N/A |
| Rate Limit | ✓ | ✓ | ✓ | ✓ |
| Domain Allowlist | N/A | N/A | N/A | ✓ |
| Device Allowlist | ✓ | ✓ | N/A | N/A |
| Command Signing | N/A | ✓ | N/A | N/A |
| Container Isolation | Optional | N/A | ✓ | ✓ |
| Audit Logging | ✓ | ✓ | ✓ | ✓ |
| User Confirmation | Destructive | Destructive | Always | Destructive |
| Legal Consent | N/A | N/A | Required | Optional |
| Credential Vault | N/A | N/A | N/A | ✓ |
| Network Isolation | N/A | Local | Air-gapped | Allowlist |

### 4.2 Detection Rules

```yaml
# Security monitoring rules
rules:
  - name: policy_bypass_attempt
    condition: |
      action.result == "denied" AND
      retry_count > 3 AND
      time_window < 60s
    severity: high
    action: alert + block_session
    
  - name: unusual_device_activity
    condition: |
      device.commands_per_minute > 100 OR
      device.error_rate > 0.5
    severity: medium
    action: alert + throttle
    
  - name: credential_access_anomaly
    condition: |
      vault.access_count > 10 AND
      time_window < 300s
    severity: high
    action: alert + require_mfa
    
  - name: container_escape_indicator
    condition: |
      syscall IN [ptrace, mount, setns] OR
      file.path.startswith("/proc/1/")
    severity: critical
    action: kill_container + alert
    
  - name: cyber_lab_external_connection
    condition: |
      network.destination NOT IN internal_ranges AND
      context.environment == "cyber_lab"
    severity: critical
    action: block + terminate_session + alert
```

---

## 5. RISK ASSESSMENT

### 5.1 Risk Matrix

| Risk | Likelihood | Impact | Score | Priority |
|------|------------|--------|-------|----------|
| Container escape | Low | Critical | High | P1 |
| Policy bypass | Medium | High | High | P1 |
| Credential theft | Low | Critical | High | P1 |
| IoT device compromise | Medium | Medium | Medium | P2 |
| Unauthorized scanning | Medium | High | High | P1 |
| Mobile app tampering | Low | Medium | Low | P3 |
| DoS via automation | Medium | Low | Low | P3 |
| Audit log tampering | Low | High | Medium | P2 |

### 5.2 Residual Risk Acceptance

| Risk | Accepted | Condition |
|------|----------|-----------|
| Container escape | Yes | With gVisor/Kata for Cyber Lab |
| IoT physical access | Yes | User's physical security |
| Mobile device theft | Yes | With remote wipe capability |
| Third-party plugin risk | No | Only signed plugins allowed |

---

## 6. SECURITY TESTING REQUIREMENTS

### 6.1 Penetration Testing Scope

```
IN SCOPE:
- Policy bypass attempts
- Trust boundary crossing
- Container escape
- Credential extraction
- Network isolation breach
- Command injection in plugins
- Session hijacking
- Privilege escalation

OUT OF SCOPE:
- Physical attacks on hardware
- Social engineering of users
- DDoS testing
- Third-party service vulnerabilities
```

### 6.2 Automated Security Tests

```python
# Required test categories
security_tests = [
    "test_policy_denies_unauthorized_domain",
    "test_container_cannot_access_host_filesystem",
    "test_credentials_never_in_logs",
    "test_iot_command_requires_valid_signature",
    "test_cyber_lab_cannot_reach_external",
    "test_rate_limit_blocks_abuse",
    "test_session_cannot_be_reused_after_logout",
    "test_audit_log_detects_tampering",
    "test_mobile_cert_pinning_enforced",
    "test_plugin_cannot_escalate_capabilities",
]
```

---

*Document Version: 1.0*
*Classification: INTERNAL*
*Review Required: Annually or after security incident*
