#!/usr/bin/env bash

repo_api_path() {
  local repo="$1"
  printf 'repos/%s' "$repo"
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
