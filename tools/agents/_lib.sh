#!/usr/bin/env bash

repo_api_path() {
  local repo="$1"
  printf 'repos/%s' "$repo"
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
