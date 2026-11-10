#pragma once
#include "BodyMeasurements.h"
#include "StylePreferences.h"
#include "UserProfile.h"
namespace mirage::profile
{
class UserProfileAggregate
{
    UserProfile profile_;
    StylePreferences preferences_;
    std::optional<BodyMeasurements> measurements_;

  public:
    explicit UserProfileAggregate(UserProfile profile, StylePreferences preferences = {},
                                  std::optional<BodyMeasurements> measurements = std::nullopt);
    const UserProfile &profile() const
    {
        return profile_;
    }
    const StylePreferences &preferences() const
    {
        return preferences_;
    }
    const std::optional<BodyMeasurements> &measurements() const
    {
        return measurements_;
    }
    bool belongsTo(const std::string &userId) const
    {
        return profile_.userId == userId;
    }
    void updateProfile(std::string name, std::optional<std::string> birthDate,
                       std::optional<std::string> imageUrl);
    void updatePreferences(StylePreferences preferences);
    void registerMeasurements(BodyMeasurements measurements);
};
} // namespace mirage::profile
