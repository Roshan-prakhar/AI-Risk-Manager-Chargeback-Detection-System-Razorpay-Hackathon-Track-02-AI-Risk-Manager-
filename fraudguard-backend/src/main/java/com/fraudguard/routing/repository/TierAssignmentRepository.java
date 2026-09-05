package com.fraudguard.routing.repository;

import com.fraudguard.routing.model.TierAssignment;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface TierAssignmentRepository extends JpaRepository<TierAssignment, Long> {
}
