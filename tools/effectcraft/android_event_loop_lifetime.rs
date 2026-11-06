//! One live Android event loop at a time, released with its Activity's native resources.
use std::sync::atomic::{AtomicBool, Ordering};

static LIVE: AtomicBool = AtomicBool::new(false);

pub(crate) struct AndroidEventLoopLifetime;

impl AndroidEventLoopLifetime {
    pub(crate) fn acquire() -> Option<Self> {
        LIVE.compare_exchange(false, true, Ordering::AcqRel, Ordering::Acquire)
            .ok().map(|_| Self)
    }
}

impl Drop for AndroidEventLoopLifetime {
    fn drop(&mut self) {
        LIVE.store(false, Ordering::Release);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn relaunch_releases_only_after_native_resources_drop() {
        struct NativeResources;
        impl Drop for NativeResources {
            fn drop(&mut self) {
                assert!(AndroidEventLoopLifetime::acquire().is_none());
            }
        }
        struct ActivityLoop {
            _resources: NativeResources,
            _lifetime: AndroidEventLoopLifetime,
        }
        for _ in 0..100 {
            let lifetime = AndroidEventLoopLifetime::acquire().unwrap();
            assert!(AndroidEventLoopLifetime::acquire().is_none());
            let activity = ActivityLoop { _resources: NativeResources, _lifetime: lifetime };
            drop(activity);
        }
        // Failed construction also releases the reservation through RAII.
        fn failed_construction() -> Result<(), ()> {
            let _lifetime = AndroidEventLoopLifetime::acquire().ok_or(())?;
            Err(())
        }
        assert!(failed_construction().is_err());
        assert!(AndroidEventLoopLifetime::acquire().is_some());
    }
}
