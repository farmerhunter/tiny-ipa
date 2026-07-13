#!/usr/bin/env bash

repo_api_path() {
  local repo="$1"
  printf 'repos/%s' "$repo"
}

agent_role_config_path() {
  if [[ -n "${AGENT_ROLE_ROUTING_CONFIG:-}" ]]; then
    printf '%s\n' "$AGENT_ROLE_ROUTING_CONFIG"
    return
  fi

  local lib_dir
  lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  printf '%s/role-routing.conf\n' "$lib_dir"
}

agent_set_default_role_config() {
  AGENT_ROLES=(architect implementer tester reviewer user ci merge)
  AGENT_ROLE_LABEL_architect="needs:architect"
  AGENT_ROLE_LABEL_implementer="needs:implementer"
  AGENT_ROLE_LABEL_tester="needs:tester"
  AGENT_ROLE_LABEL_reviewer="needs:reviewer"
  AGENT_ROLE_LABEL_user="needs:user"
  AGENT_ROLE_LABEL_ci="needs:ci"
  AGENT_ROLE_LABEL_merge="needs:merge"
  AGENT_PRIMARY_NEXT_LABELS=(
    needs:architect
    needs:implementer
    needs:tester
    needs:reviewer
    needs:user
    needs:ci
    needs:merge
    blocked
  )
  AGENT_ROLE_CONFIG_SOURCE="built-in fallback"
}

agent_fail_config() {
  printf 'Invalid agent role routing config: %s\n' "$1" >&2
  return 2
}

agent_contains_value() {
  local needle="$1"
  shift
  local value

  for value in "$@"; do
    if [[ "$value" == "$needle" ]]; then
      return 0
    fi
  done

  return 1
}

agent_join_lines() {
  awk 'BEGIN { first = 1 } { if (!first) printf ", "; printf "%s", $0; first = 0 }'
}

agent_validate_role_config() {
  local role label var_name primary seen matched

  if ! declare -p AGENT_ROLES >/dev/null 2>&1; then
    agent_fail_config "AGENT_ROLES must be defined"
    return 2
  fi
  if ! declare -p AGENT_PRIMARY_NEXT_LABELS >/dev/null 2>&1; then
    agent_fail_config "AGENT_PRIMARY_NEXT_LABELS must be defined"
    return 2
  fi
  if (( ${#AGENT_ROLES[@]} == 0 )); then
    agent_fail_config "AGENT_ROLES must not be empty"
    return 2
  fi
  if (( ${#AGENT_PRIMARY_NEXT_LABELS[@]} == 0 )); then
    agent_fail_config "AGENT_PRIMARY_NEXT_LABELS must not be empty"
    return 2
  fi

  seen=""
  for role in "${AGENT_ROLES[@]}"; do
    if [[ ! "$role" =~ ^[a-z][a-z0-9_]*$ ]]; then
      agent_fail_config "unsupported role name '$role'"
      return 2
    fi
    if grep -Fxq "$role" <<< "$seen"; then
      agent_fail_config "duplicate role '$role'"
      return 2
    fi
    seen="${seen}${role}"$'\n'

    var_name="AGENT_ROLE_LABEL_$role"
    eval "label=\"\${$var_name:-}\""
    if [[ -z "$label" ]]; then
      agent_fail_config "missing $var_name"
      return 2
    fi
    if [[ ! "$label" =~ ^needs:[a-z][a-z0-9_]*$ ]]; then
      agent_fail_config "$var_name must be a needs:<role> label: $label"
      return 2
    fi
    if ! agent_contains_value "$label" "${AGENT_PRIMARY_NEXT_LABELS[@]}"; then
      agent_fail_config "$var_name is not listed in AGENT_PRIMARY_NEXT_LABELS: $label"
      return 2
    fi
  done

  seen=""
  for primary in "${AGENT_PRIMARY_NEXT_LABELS[@]}"; do
    if [[ "$primary" != "blocked" && ! "$primary" =~ ^needs:[a-z][a-z0-9_]*$ ]]; then
      agent_fail_config "unsupported primary next-action label '$primary'"
      return 2
    fi
    if grep -Fxq "$primary" <<< "$seen"; then
      agent_fail_config "duplicate primary next-action label '$primary'"
      return 2
    fi
    seen="${seen}${primary}"$'\n'

    if [[ "$primary" == needs:* ]]; then
      matched=0
      for role in "${AGENT_ROLES[@]}"; do
        var_name="AGENT_ROLE_LABEL_$role"
        eval "label=\"\${$var_name:-}\""
        if [[ "$label" == "$primary" ]]; then
          matched=1
          break
        fi
      done
      if [[ "$matched" -eq 0 ]]; then
        agent_fail_config "primary label has no configured role: $primary"
        return 2
      fi
    fi
  done
}

agent_load_role_config() {
  if [[ "${AGENT_ROLE_CONFIG_LOADED:-0}" -eq 1 ]]; then
    return
  fi

  local config_path
  config_path="$(agent_role_config_path)"
  if [[ -f "$config_path" ]]; then
    unset AGENT_ROLES AGENT_PRIMARY_NEXT_LABELS
    while IFS= read -r var_name; do
      unset "$var_name"
    done < <(compgen -A variable AGENT_ROLE_LABEL_ || true)

    # shellcheck source=/dev/null
    source "$config_path"
    AGENT_ROLE_CONFIG_SOURCE="$config_path"
  else
    agent_set_default_role_config
  fi

  agent_validate_role_config || return 2
  AGENT_ROLE_CONFIG_LOADED=1
}

agent_configured_roles() {
  local role
  agent_load_role_config || return 2
  for role in "${AGENT_ROLES[@]}"; do
    printf '%s\n' "$role"
  done
}

agent_primary_next_labels() {
  local label
  agent_load_role_config || return 2
  for label in "${AGENT_PRIMARY_NEXT_LABELS[@]}"; do
    printf '%s\n' "$label"
  done
}

agent_role_exists() {
  local target="$1"
  local role
  agent_load_role_config || return 2
  for role in "${AGENT_ROLES[@]}"; do
    if [[ "$role" == "$target" ]]; then
      return 0
    fi
  done
  return 1
}

agent_role_label_for_role() {
  local role="$1"
  local var_name label

  agent_load_role_config || return 2
  if ! agent_role_exists "$role"; then
    printf 'Unknown agent role: %s\n' "$role" >&2
    printf 'Configured roles: %s\n' "$(agent_configured_roles | agent_join_lines)" >&2
    return 2
  fi

  var_name="AGENT_ROLE_LABEL_$role"
  eval "label=\"\${$var_name:-}\""
  printf '%s\n' "$label"
}

agent_is_primary_next_label() {
  local target="$1"
  local label

  agent_load_role_config || return 2
  for label in "${AGENT_PRIMARY_NEXT_LABELS[@]}"; do
    if [[ "$label" == "$target" ]]; then
      return 0
    fi
  done

  return 1
}

agent_require_primary_next_label() {
  local label="$1"

  agent_load_role_config || return 2
  if ! agent_contains_value "$label" "${AGENT_PRIMARY_NEXT_LABELS[@]}"; then
    printf 'Unsupported next-action label: %s\n' "$label" >&2
    printf 'Configured primary next-action labels: %s\n' "$(agent_primary_next_labels | agent_join_lines)" >&2
    return 2
  fi
}

agent_label_for_inbox_target() {
  local target="$1"

  agent_load_role_config || return 2
  if agent_role_exists "$target"; then
    agent_role_label_for_role "$target"
    return
  fi
  if agent_is_primary_next_label "$target"; then
    printf '%s\n' "$target"
    return
  fi

  printf 'Unknown inbox target: %s\n' "$target" >&2
  printf 'Use a configured role, primary next-action label, or all.\n' >&2
  return 2
}

agent_print_role_routing_config() {
  local role label first=1

  agent_load_role_config || return 2
  printf 'Config: %s\n' "$AGENT_ROLE_CONFIG_SOURCE"
  printf 'Roles:'
  for role in "${AGENT_ROLES[@]}"; do
    label="$(agent_role_label_for_role "$role")"
    printf ' %s=%s' "$role" "$label"
  done
  printf '\n'
  printf 'Primary next-action labels: '
  for label in "${AGENT_PRIMARY_NEXT_LABELS[@]}"; do
    if [[ "$first" -eq 1 ]]; then
      first=0
    else
      printf ', '
    fi
    printf '%s' "$label"
  done
  printf '\n'
}

require_number() {
  local value="$1"
  local name="$2"

  if [[ ! "$value" =~ ^[0-9]+$ ]]; then
    printf '%s must be a number: %s\n' "$name" "$value" >&2
    return 2
  fi
}

extract_contract_line() {
  local prefix="$1"
  local text="$2"

  awk -v prefix="$prefix" '
    index($0, prefix) == 1 {
      print
      found = 1
      exit
    }
    END {
      if (!found) {
        print prefix " MISSING"
      }
    }
  ' <<< "$text"
}

extract_contract_value() {
  local prefix="$1"
  local text="$2"
  local line

  line="$(extract_contract_line "$prefix" "$text")"
  if [[ "$line" == "$prefix MISSING" ]]; then
    printf 'MISSING\n'
    return
  fi

  sed -E "s/^${prefix//\//\\/}[[:space:]]*//" <<< "$line"
}

contract_role_value_state() {
  local value="$1"

  case "$value" in
    MISSING)
      printf 'missing'
      ;;
    none)
      printf 'none'
      ;;
    "")
      printf 'malformed'
      ;;
    *)
      if [[ ! "$value" =~ ^[a-z][a-z0-9_]*$ ]]; then
        printf 'malformed'
      elif agent_role_exists "$value"; then
        printf 'ok'
      else
        printf 'unknown role'
      fi
      ;;
  esac
}

contract_handoff_value_state() {
  local value="$1"
  local role

  case "$value" in
    MISSING)
      printf 'missing'
      ;;
    none)
      printf 'none'
      ;;
    "batch checkpoint"|"close after evidence"|hold)
      printf 'ok'
      ;;
    to:*)
      role="${value#to:}"
      if [[ -z "$role" || ! "$role" =~ ^[a-z][a-z0-9_]*$ ]]; then
        printf 'malformed'
      elif agent_role_exists "$role"; then
        printf 'ok'
      else
        printf 'unknown role'
      fi
      ;;
    "")
      printf 'malformed'
      ;;
    *)
      printf 'unknown value'
      ;;
  esac
}

contract_role_field_report() {
  local contract="$1"
  local owner review acceptance handoff

  owner="$(extract_contract_value "Owner role:" "$contract")"
  review="$(extract_contract_value "Review role:" "$contract")"
  acceptance="$(extract_contract_value "Acceptance role:" "$contract")"
  handoff="$(extract_contract_value "Completion handoff:" "$contract")"

  printf 'Owner role: %s [%s]\n' "$owner" "$(contract_role_value_state "$owner")"
  printf 'Review role: %s [%s]\n' "$review" "$(contract_role_value_state "$review")"
  printf 'Acceptance role: %s [%s]\n' "$acceptance" "$(contract_role_value_state "$acceptance")"
  printf 'Completion handoff: %s [%s]\n' "$handoff" "$(contract_handoff_value_state "$handoff")"
}

extract_latest_contract_block() {
  local text="$1"

  awk '
    function priority(header) {
      if (header == "Final Execution Contract") return 3
      if (header == "Execution Contract") return 2
      if (header == "Draft Execution Contract") return 1
      return 0
    }
    function flush_current() {
      if (!in_contract) return
      if (current_priority > best_priority ||
          (current_priority == best_priority && current_order > best_order)) {
        best_priority = current_priority
        best_order = current_order
        best_block = current_block
      }
    }

    /^## (Final Execution Contract|Execution Contract|Draft Execution Contract)[[:space:]]*$/ {
      flush_current()
      in_contract = 1
      current_order += 1
      current_header = $0
      sub(/^## /, "", current_header)
      current_priority = priority(current_header)
      current_block = $0 "\n"
      next
    }

    /^## / {
      flush_current()
      in_contract = 0
      current_block = ""
      current_priority = 0
      next
    }

    {
      if (in_contract) {
        current_block = current_block $0 "\n"
      }
    }

    END {
      flush_current()
      if (best_block != "") {
        printf "%s", best_block
      }
    }
  ' <<< "$text"
}

contract_header() {
  local text="$1"

  awk '
    /^## (Final Execution Contract|Execution Contract|Draft Execution Contract)[[:space:]]*$/ {
      sub(/^## /, "")
      print
      found = 1
      exit
    }
    END {
      if (!found) {
        print "Execution Contract MISSING"
      }
    }
  ' <<< "$text"
}
