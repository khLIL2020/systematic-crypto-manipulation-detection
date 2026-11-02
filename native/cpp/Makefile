CXX ?= clang++
CXXFLAGS ?= -std=c++17 -O3 -fPIC -Wall -Wextra
LDFLAGS_SHARED ?= -shared

UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
  TARGET := ../../backend/native_lib/libscore_engine.dylib
  LDFLAGS_SHARED += -dynamiclib
else
  TARGET := ../../backend/native_lib/libscore_engine.so
endif

.PHONY: all clean

all: $(TARGET)

$(TARGET): score_engine.cpp score_engine.h
	mkdir -p $(dir $(TARGET))
	$(CXX) $(CXXFLAGS) $(LDFLAGS_SHARED) -o $(TARGET) score_engine.cpp

clean:
	rm -f $(TARGET)
