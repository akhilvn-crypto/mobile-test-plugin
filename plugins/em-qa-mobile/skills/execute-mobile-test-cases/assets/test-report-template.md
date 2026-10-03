---
title: "{{title}}"
document_type: Test Report
project_id:
document_id:
version: {{version}}
approved_date:
privacy: Confidential
tags:
  - test-report
  - qa
  - mobile
  - {{platform_tag}}
  - flutter
---

# {{plan_name}} – {{platform_name}} Test Report

| Field | Value |
|---|---|
| Test plan | {{plan_name}} |
| Test case file | {{testcase_file}} |
| Platform | {{platform_name}} |
| Device | {{device}} |
| OS version | {{os_version}} |
| App version and build | {{build}} |
| Environment | {{environment}} |
| Network | {{network}} |
| Execution date (IST) | {{execution_date}} |
| Executed by | |
| Overall testing by lead | |

Out of scope for now: API, security and accessibility

## Summary

{{summary}}

## Results at a glance

| Result | Count |
|---|---|
| Passed | {{passed}} |
| Failed | {{failed}} |
| Total (Passed+Failed) | {{executed}} |
| Unexecuted | {{unexecuted}} |
| In Progress | {{in_progress}} |
| Blocked | {{blocked}} |
| Total | {{total}} |

## Results by test suite

{{suites_intro}}

{{suites}}

## Defects raised

{{defects}}

## Blocked and unexecuted cases

{{blocked_unexecuted}}

## Observations

{{observations}}

## UX suggestions

{{ux_suggestions}}
