#!/usr/bin/env bash
# Shared terminal UI. All output goes to stderr so stdout remains machine-readable.

ps04_ui_init() {
  if [[ -t 2 && -z ${NO_COLOR:-} ]]; then
    PS04_BOLD=$'\033[1m'
    PS04_DIM=$'\033[2m'
    PS04_BLUE=$'\033[34m'
    PS04_GREEN=$'\033[32m'
    PS04_YELLOW=$'\033[33m'
    PS04_RED=$'\033[31m'
    PS04_RESET=$'\033[0m'
  else
    PS04_BOLD=''; PS04_DIM=''; PS04_BLUE=''; PS04_GREEN=''; PS04_YELLOW=''; PS04_RED=''; PS04_RESET=''
  fi
}

ps04_banner() {
  [[ ${PS04_PROGRESS:-1} == 0 ]] && return
  printf '\n%s%s┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓%s\n' "$PS04_BOLD" "$PS04_BLUE" "$PS04_RESET" >&2
  printf '%s%s┃  %-50s┃%s\n' "$PS04_BOLD" "$PS04_BLUE" "$1" "$PS04_RESET" >&2
  printf '%s%s┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛%s\n' "$PS04_BOLD" "$PS04_BLUE" "$PS04_RESET" >&2
}

ps04_step() {
  [[ ${PS04_PROGRESS:-1} == 0 ]] && return
  printf '\n%s%s[%s/%s]%s %s%s%s\n' "$PS04_BOLD" "$PS04_BLUE" "$1" "$2" "$PS04_RESET" "$PS04_BOLD" "$3" "$PS04_RESET" >&2
  [[ -n ${4:-} ]] && printf '      %s%s%s\n' "$PS04_DIM" "$4" "$PS04_RESET" >&2
}

ps04_info() {
  [[ ${PS04_PROGRESS:-1} == 0 ]] && return
  printf '      %s→%s %s\n' "$PS04_BLUE" "$PS04_RESET" "$1" >&2
}

ps04_ok() {
  [[ ${PS04_PROGRESS:-1} == 0 ]] && return
  printf '      %s✓%s %s\n' "$PS04_GREEN" "$PS04_RESET" "$1" >&2
}

ps04_warn() {
  [[ ${PS04_PROGRESS:-1} == 0 ]] && return
  printf '      %s!%s %s\n' "$PS04_YELLOW" "$PS04_RESET" "$1" >&2
}

ps04_fail() {
  [[ ${PS04_PROGRESS:-1} == 0 ]] && return
  printf '      %s✗%s %s\n' "$PS04_RED" "$PS04_RESET" "$1" >&2
}

ps04_file_count() {
  local path=$1
  if [[ -f "$path" ]]; then
    sed '/^[[:space:]]*$/d' "$path" | wc -l | tr -d ' '
  else
    printf '0'
  fi
}

ps04_ui_init
