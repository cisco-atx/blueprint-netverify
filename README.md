<div>
<img src="https://raw.githubusercontent.com/cisco-atx/blueprint-netverify/refs/heads/main/netverify.ico" width="64">
</div>

# NetVerify
>Compare Validate And Assure

## Overview

NetVerify is a network validation and assurance module within the ATX (Automation Tooling) platform.

It is designed to automate pre-migration and post-migration verification activities by collecting network state snapshots, comparing device configurations, validating endpoint connectivity, and verifying routing consistency.

NetVerify helps network engineers reduce manual validation effort, accelerate migration execution, and improve confidence during infrastructure changes.

---

## Why NetVerify?

Network migrations often require engineers to answer critical questions after a change:

- Did the device configuration change as expected?
- Are all endpoints still reachable?
- Have any hosts moved unexpectedly?
- Were VLAN assignments preserved?
- Did routing entries change?
- Were next-hop paths altered?
- Is the network operating the same way after migration?

Traditionally these checks are performed manually by collecting CLI outputs before and after a migration and comparing them line-by-line.

NetVerify automates this process by capturing device snapshots, storing structured baseline data, and generating validation reports that highlight meaningful differences.

---

## NetVerify in ATX

NetVerify is implemented as a Flask Blueprint and integrates directly into the ATX platform.

### Blueprint Metadata

| Property | Value |
|-----------|---------|
| Name | NetVerify |
| Version | 1.0.0 |
| URL Prefix | `/netverify` |
| Description | Compare Validate And Assure |

---

## Core Capabilities

### Snapshot Collection

NetVerify captures operational data from network devices and stores it as reusable JSON snapshots.

Snapshots can be collected:

- Before a migration (Pre Snapshot)
- After a migration (Post Snapshot)

Each snapshot contains:

- Device metadata
- Device type
- Hostname / prompt information
- Command outputs
- Snapshot metadata
- Collection timestamp

### Parallel Data Collection

Snapshots are collected concurrently using a ThreadPoolExecutor, allowing multiple devices to be queried simultaneously and significantly reducing collection time during large migration events.

### Jump Host Support

Device connectivity is performed through a configurable jump host (proxy), making NetVerify suitable for secured enterprise environments where direct device access is restricted.

---

## Snapshot Data Collection

By default, NetVerify collects the following commands:

```text
show run
show interface status
show mac address-table dynamic
show ip route
show ip arp
```

Additional custom commands can be supplied during snapshot creation.

---

## Validation Modules

NetVerify currently supports three validation engines.

### 1. Configuration Validation

Purpose:

Compare device configurations before and after migration.

Source Command:

```text
show run
```

Capabilities:

- Hierarchical configuration comparison
- Detection of added configuration
- Detection of removed configuration
- Detection of modified configuration
- Context-aware comparison using configuration hierarchy
- Visual HTML diff reporting

Example Use Cases:

- Switch replacement
- Core migration
- Access layer refresh
- Data center migration

---

### 2. Endpoint Validation

Purpose:

Validate that connected endpoints remain operational after migration.

Data Sources:

```text
show mac address-table dynamic
show ip arp
show interface status
```

Validation Criteria:

- MAC Address
- VLAN
- IP Address
- Hostname
- Device
- Interface
- Speed
- Duplex

Capabilities:

- Endpoint discovery
- Endpoint movement detection
- VLAN consistency validation
- Host relocation identification
- Interface change tracking
- Speed/Duplex verification

Example Use Cases:

- Access switch migration
- Campus refresh projects
- Building migrations
- Floor-by-floor network upgrades

---

### 3. Route Validation

Purpose:

Verify routing consistency before and after migration.

Source Command:

```text
show ip route
```

Validation Criteria:

- Prefix existence
- Next-hop changes
- Routing protocol changes
- Interface changes
- VRF changes

Capabilities:

- Route presence verification
- Route loss detection
- Route addition detection
- ECMP path comparison
- Next-hop validation

Example Use Cases:

- Core migration
- WAN migration
- Router replacement
- Data center network transformation

---

## Migration Workflow

### Step 1 – Collect Pre-Migration Snapshot

Before making any changes:

1. Select target devices.
2. Create a Pre Snapshot.
3. Store baseline operational state.

### Step 2 – Execute Migration

Perform the planned network migration activity.

Examples:

- Device replacement
- VLAN migration
- Routing migration
- Data center cutover
- WAN transformation

### Step 3 – Collect Post-Migration Snapshot

After the migration:

1. Run a Post Snapshot.
2. Capture current network state.

### Step 4 – Run Validation

Compare:

```text
Pre Snapshot
        VS
Post Snapshot
```

Selected validation modules analyze differences and generate a report.

### Step 5 – Review Report

NetVerify generates an HTML report containing:

- Configuration differences
- Endpoint differences
- Routing differences
- Added objects
- Removed objects
- Modified objects

---

## Snapshot Architecture

### Snapshot Structure

```text
Snapshot
├── Metadata
├── Device Inventory
│   ├── Device Type
│   ├── Hostname
│   └── Command Outputs
└── Collection Timestamp
```

Snapshots are stored as JSON files and can be:

- Viewed
- Downloaded
- Reused for future comparisons
- Archived as migration evidence

---

## Report Management

Validation reports are automatically generated in HTML format.

Features include:

- Report storage
- Report viewing
- Report download
- Report deletion
- Historical comparison records

Reports provide migration evidence and can be attached to project documentation or change records.

---

## Supported Network Data Sources

NetVerify currently validates information derived from:

- Running Configuration
- MAC Address Tables
- ARP Tables
- Interface Status Tables
- Routing Tables

The framework is extensible and allows additional validation modules to be added in future releases.

---

## Benefits

### Reduced Manual Effort

Eliminates repetitive CLI collection and comparison tasks.

### Faster Validation

Allows engineers to validate large migrations in minutes instead of hours.

### Improved Accuracy

Reduces human error associated with manual comparisons.

### Consistent Verification Process

Provides a repeatable validation methodology across projects.

### Migration Assurance

Gives project teams confidence that services and network state remain consistent after change implementation.

---

## Typical Use Cases

- Access Switch Refresh
- Distribution Layer Migration
- Core Network Migration
- WAN Router Replacement
- Data Center Migration
- Network Hardware Refresh
- VLAN Migration Projects
- Campus Network Modernization
- Merger & Acquisition Network Integration
- Post-Change Validation

---

## Future Enhancements

Potential future validation modules include:

- VLAN Validation
- STP Validation
- HSRP/VRRP Validation
- BGP Neighbor Validation
- OSPF Neighbor Validation
- Interface Error Validation
- Wireless Client Validation
- Multicast Validation
- Application Reachability Testing

---

## Summary

NetVerify provides an automated framework for collecting, comparing, and validating network state before and after migration activities. By combining configuration comparison, endpoint validation, and route verification into a single workflow, NetVerify helps organizations perform network migrations with greater speed, consistency, and confidence.
