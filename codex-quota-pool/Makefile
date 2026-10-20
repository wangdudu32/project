.PHONY: check test integration install

BIN_DIR ?= $(HOME)/.local/bin

install:
	@mkdir -p "$(BIN_DIR)"
	@if [ "$$(readlink -f -- "$(BIN_DIR)/cdx")" = "$(CURDIR)/cdx" ]; then \
		printf '已安装：%s\n' "$(BIN_DIR)/cdx"; \
	else \
		ln -sT -- "$(CURDIR)/cdx" "$(BIN_DIR)/cdx"; \
	fi

check: test

test:
	python3 -m unittest discover -s tests -v

integration:
	POOL_REAL_CODEX_TEST=1 python3 -m unittest discover -s tests -v
