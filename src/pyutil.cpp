#include "duckdb_python/pyutil.hpp"

#include "duckdb/common/exception.hpp"
#include "duckdb/common/atomic.hpp"
#include "duckdb_python/pyconnection/pyconnection.hpp"

namespace duckdb {

namespace {

//! The thread that ran the exit hook, which is the one finalizing the interpreter; 0 until the hook ran
atomic<unsigned long> finalizing_thread {0};

} // namespace

bool PyUtil::CanEnterInterpreter() {
	// Py_IsInitialized turns false as finalization starts, before the thread states of other threads are removed
	if (Py_IsInitialized()) {
		return true;
	}
	const auto finalizing = finalizing_thread.load();
	if (finalizing == 0) {
		// Finalizing without the exit hook having run: only a thread with a thread state can be the one finalizing
		return PyGILState_GetThisThreadState() != nullptr;
	}
	return finalizing == PyThread_get_thread_ident();
}

void PyUtil::SetFinalizingThread() {
	finalizing_thread = PyThread_get_thread_ident();
}

#ifndef Py_LIMITED_API
bool PyUtil::GilCheck() {
	// Not PyGILState_Check, which answers true on every thread once any subinterpreter has been created.
#if PY_VERSION_HEX >= 0x030D0000
	return PyThreadState_GetUnchecked() != nullptr;
#elif PY_VERSION_HEX >= 0x030C0000
	return _PyThreadState_UncheckedGet() != nullptr;
#else
	// Before 3.12 the current thread state is process wide, so it must also be this thread's own.
	auto current = _PyThreadState_UncheckedGet();
	return current && current == PyGILState_GetThisThreadState();
#endif
}
#endif

bool PyUtil::IsListLike(nb::handle obj) {
	if (nb::isinstance<nb::str>(obj) || nb::isinstance<nb::bytes>(obj)) {
		return false;
	}
	if (IsDictLike(obj)) {
		return false;
	}
	auto &import_cache = *DuckDBPyConnection::ImportCache();
	auto iterable = import_cache.collections.abc.Iterable();
	return IsInstance(obj, iterable);
}

bool PyUtil::IsDictLike(nb::handle obj) {
	auto &import_cache = *DuckDBPyConnection::ImportCache();
	auto mapping = import_cache.collections.abc.Mapping();
	return IsInstance(obj, mapping);
}

} // namespace duckdb
