#pragma once
#include "../domain/repositories/ProfileRepository.h"
namespace mirage::profile
{
class SupabaseProfileRepository final : public ProfileRepository
{
  public:
    void findByUserId(const ProfileAccess &, ProfileCompletion) const override;
    void create(const ProfileAccess &, const UserProfileAggregate &,
                ProfileCompletion) const override;
    void updateProfile(const ProfileAccess &, const UserProfileAggregate &,
                       ProfileCompletion) const override;
    void updatePreferences(const ProfileAccess &, const StylePreferences &,
                           ProfileCompletion) const override;
    void saveMeasurements(const ProfileAccess &, const BodyMeasurements &,
                          ProfileCompletion) const override;
};
} // namespace mirage::profile
