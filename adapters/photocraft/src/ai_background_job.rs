//! PhotoCraft AI background-removal job lifecycle foundation.
//! This module deliberately does not perform network I/O or mutate a document.
//! Only a fully decoded, owner-approved image can later be committed through
//! the editor's undo transaction. This state machine prevents stale results
//! from being applied after cancellation or document switches.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct JobId(pub u64);
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct DocumentRevision { pub document: u64, pub revision: u64 }
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum JobState { Idle, AwaitingConsent, Running, Ready, Cancelled, Failed }
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Job {
    pub id: JobId,
    pub origin: DocumentRevision,
    pub state: JobState,
}
impl Job {
    pub fn new(id: JobId, origin: DocumentRevision) -> Self {
        Self { id, origin, state: JobState::AwaitingConsent }
    }
    pub fn consent(&mut self) -> Result<(), &'static str> {
        if self.state != JobState::AwaitingConsent { return Err("Job is not awaiting consent"); }
        self.state = JobState::Running;
        Ok(())
    }
    pub fn finish(&mut self, id: JobId) -> Result<(), &'static str> {
        if self.id != id || self.state != JobState::Running { return Err("Stale or inactive job result"); }
        self.state = JobState::Ready;
        Ok(())
    }
    pub fn may_insert(&self, current: DocumentRevision) -> bool {
        self.state == JobState::Ready && self.origin == current
    }
    pub fn cancel(&mut self) {
        if !matches!(self.state, JobState::Cancelled | JobState::Failed) {
            self.state = JobState::Cancelled;
        }
    }
    pub fn fail(&mut self) {
        if !matches!(self.state, JobState::Cancelled | JobState::Ready) {
            self.state = JobState::Failed;
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    const DOC: DocumentRevision = DocumentRevision { document: 7, revision: 3 };
    #[test] fn consent_required() {
        let mut job = Job::new(JobId(1), DOC);
        assert!(job.finish(JobId(1)).is_err());
        assert!(job.consent().is_ok());
        assert!(job.finish(JobId(1)).is_ok());
        assert!(job.may_insert(DOC));
    }
    #[test] fn stale_job_rejected() {
        let mut job = Job::new(JobId(1), DOC);
        job.consent().unwrap();
        assert!(job.finish(JobId(2)).is_err());
        job.finish(JobId(1)).unwrap();
        assert!(!job.may_insert(DocumentRevision { document: 8, revision: 3 }));
        assert!(!job.may_insert(DocumentRevision { document: 7, revision: 4 }));
    }
    #[test] fn cancellation_prevents_insertion() {
        let mut job = Job::new(JobId(1), DOC);
        job.consent().unwrap();
        job.cancel();
        assert!(job.finish(JobId(1)).is_err());
        assert!(!job.may_insert(DOC));
    }
    #[test] fn failure_prevents_insertion() {
        let mut job = Job::new(JobId(1), DOC);
        job.consent().unwrap();
        job.fail();
        assert!(!job.may_insert(DOC));
    }
}
