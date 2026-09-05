package com.fraudguard.verifier.repository;

import com.fraudguard.verifier.model.DisputeVerdict;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

/** Spring Data repository for persisting and querying dispute verdicts. */
public interface DisputeVerdictRepository extends JpaRepository<DisputeVerdict, Long> {

    List<DisputeVerdict> findByTransactionId(Long transactionId);
}
