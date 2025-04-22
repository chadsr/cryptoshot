# CryptoShot

[![CI](https://github.com/chadsr/cryptoshot/actions/workflows/ci.yml/badge.svg)](https://github.com/chadsr/cryptoshot/actions/workflows/ci.yml)

Retrieve cryptocurrency balances and values at a specific point in time

## Setup

```shell
poetry install
```

## Configuration

```shell
cp config.example.json config.json
```

Once copied, fill out any relevant addresses, API keys and other options.

## Usage

```shell
poetry run cryptoshot get -b -p --json -d "01-01-2024T00:00:00" -t "Europe/Amsterdam"
```
