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
