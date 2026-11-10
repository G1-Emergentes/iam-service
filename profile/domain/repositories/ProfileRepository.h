#pragma once
#include "../model/UserProfileAggregate.h"
#include <functional>
namespace mirage::profile
{
struct ProfileResult
{
    int status;
    std::optional<UserProfileAggregate> aggregate;
    std::string error;
};
using ProfileCompletion = std::function<void(ProfileResult)>;
// Credentials stay in the request context and are never persisted in the aggregate.
struct ProfileAccess
{
    std::string userId, bearer;
};
class ProfileRepository
{
  public:
    virtual ~ProfileRepository() = default;
    virtual void findByUserId(const ProfileAccess &, ProfileCompletion) const = 0;
    virtual void create(const ProfileAccess &, const UserProfileAggregate &,
                        ProfileCompletion) const = 0;
    virtual void updateProfile(const ProfileAccess &, const UserProfileAggregate &,
                               ProfileCompletion) const = 0;
    virtual void updatePreferences(const ProfileAccess &, const StylePreferences &,
                                   ProfileCompletion) const = 0;
    virtual void saveMeasurements(const ProfileAccess &, const BodyMeasurements &,
                                  ProfileCompletion) const = 0;
};
} // namespace mirage::profile
