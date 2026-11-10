#pragma once
#include "../domain/model/UserProfileAggregate.h"
#include <json/json.h>
namespace mirage::profile
{
class ProfileJsonMapper
{
  public:
    static Json::Value toJson(const UserProfileAggregate &);
    static Json::Value toJson(const StylePreferences &);
    static Json::Value toJson(const BodyMeasurements &);
    static UserProfileAggregate fromJson(const Json::Value &);
    static StylePreferences preferences(const Json::Value &);
    static BodyMeasurements measurements(const Json::Value &);
    static std::optional<std::string> optionalText(const Json::Value &, const char *);
    static std::string text(const Json::Value &, const char *);
};
} // namespace mirage::profile
